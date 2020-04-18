import os
from wcmatch.pathlib import Path, PurePath, SPLIT
import shutil
from zipfile import ZipFile
import re
import imgkit
from html.entities import entitydefs

# imgkit options
config = imgkit.config(wkhtmltoimage='c:/Program Files/wkhtmltopdf/bin/wkhtmltoimage.exe')
options = {
    'quiet': '',
    'format': 'jpg',
    'width': 350
}
render_head="""<head>
<meta "charset=utf-8">
</head>
"""
# fix special characters that Sakai exports
def fix_special_chars(html_text):
    leave_these = ['amp','frasl','gt','lt','quot']
    for k,v in entitydefs.items():
        if k not in leave_these:
            if v in html_text:
                html_text=html_text.replace(v,"&"+k+";")
    html_text=html_text.replace('∙',"&#8729;")
    return html_text

# accepted export file formats
TESTGEN_SAKAI = 1
TESTGEN_CANVAS = 2
SAKAI = 3
CANVAS = 4
format_names = {
#    TESTGEN_CANVAS: 'Testgen export for Canvas',
#    CANVAS: 'Canvas export',
    TESTGEN_SAKAI: 'Testgen export for sakai (TRACS)',
    SAKAI: 'TRACS (sakai) export'
    }
# directory that appears in the root directory of the zip to identify the file format
distinguishing_directory = {
    'group' : TESTGEN_SAKAI,
    'x-webct-vista-v0' : TESTGEN_CANVAS,
    'attachment' : SAKAI,
    'Quiz Files' : CANVAS
    }

# directories where files go
queue_dir = Path("queue/")
temp_dir = Path("temp/")
queue_completed_dir = Path("queue_completed/")
processed_dir = Path("processed/")
queue_dir.mkdir(exist_ok=True)
temp_dir.mkdir(exist_ok=True)
queue_completed_dir.mkdir(exist_ok=True)
processed_dir.mkdir(exist_ok=True)


# read files from queue_dir
print("reading files")
for zipfilename in queue_dir.glob('*.zip'):
    export_format = 0
    abort_zip = False
    temp_zipdir = temp_dir / zipfilename.stem
    with ZipFile(zipfilename, 'r') as zipObj:
        compress_type = zipObj.infolist()[0].compress_type
        print()
        if temp_zipdir.exists():
            print("deleting existing "+ str(temp_zipdir))
            shutil.rmtree(temp_zipdir)
        print("unzipping "+ str(zipfilename))
        zipObj.extractall(path=temp_zipdir)

        # determine the format from the directory structure.
        for dir in distinguishing_directory.keys():
            possible_dir = temp_zipdir / PurePath(dir)
            if possible_dir.exists():
                if export_format:
                    print("error: ambiguous format - try renaming your assessment/quiz and exporting again.")
                    abort_zip = True
                else:
                    export_format = distinguishing_directory[dir]
        if not export_format:
            print("error: format does not appear to be one of the accepted types: ")
            print(format_names.values())
            continue
        if abort_zip:
            continue
        print("file is of type: "+format_names[export_format])

        # find the manifest
        manifest_file = ""
        manifest = {}        
        for this_file in temp_zipdir.rglob('imsmanifest.xml'):
            if manifest_file != "":
                print("two manifests - only export one assessment per file.  skipping")
                abort_zip = True
                break
            manifest_file = this_file
            print("got manifest: "+ str(manifest_file))
        if abort_zip:
            continue


        # things that may vary depending on format
        if export_format == TESTGEN_SAKAI:
            #     testgen export - sakai format
            img_URL_prefix = "/access/content/"
            img_file_prefix = PurePath("")
            question_text_pattern = "<mattext.*?><\!\[CDATA\[(.+?)\]\]></mattext>"
        elif export_format == SAKAI:
            #    sakai export
            img_URL_prefix = "https://tracs.txstate.edu:443/access/content/"
            img_file_prefix = PurePath("")
            question_text_pattern = "<mattext.*?><\!\[CDATA\[(.+?)\]\]></mattext>"
        elif export_format == TESTGEN_CANVAS:
            #    testgen export - qti (canvas) format 
            img_URL_prefix = "/webct/RelativeResourceManager/Template/Imported_Resources/"+str(zipfilename.name)+"/"
            img_file_prefix =  PurePath("x-webct-vista-v0/")
            question_text_pattern = "<mattext.*?>(.+?)</mattext>"
        elif export_format == CANVAS:
            #    canvas qti export
            img_URL_prefix = "%24IMS-CC-FILEBASE%24/"
            img_file_prefix = PurePath("")
            question_text_pattern = "<mattext.*?>(.+?)</mattext>"
        question_text_re = re.compile(question_text_pattern)
        img_id_pattern = '<item .*?ident="(.+?)"'
        img_id_re = re.compile(img_id_pattern)
        embedded_img_pattern = '<img src="'+img_URL_prefix
        embedded_img_re = re.compile(embedded_img_pattern)
        embedded_img_sub = '<img src="'+str((temp_zipdir / img_file_prefix).resolve().as_uri())+'/'

        # look for an existing image directory to put new images into.
        #    Maybe ought to generate a new random string of letters?
        img_dir = ""
        #img_URL_dir = ""
        for img_file in temp_zipdir.rglob('*.jpg|*.pdf|*.png|*.gif',flags=SPLIT):
            #print(img_file)
            img_dir = img_file.parent
            #print (img_dir)
            #img_URL_dir = re.sub(temp_zipdir,"",img_dir)
            #print (img_URL_dir)
            break


        for xml_file in temp_zipdir.rglob('*.xml'):
            if xml_file == manifest_file:
                continue
            print("processing "+ str(xml_file))
            print()
            new_xml_file = xml_file.parent / Path('new_'+str(xml_file.name))
            #print(new_xml_file)
            xml_contents = xml_file.read_text()
            img_id = ""
            img_subid = 0

            manifest_imgs = {}

            with open(xml_file, 'r', encoding='utf-8') as old_f:
                with open(new_xml_file, 'w') as new_f:
                    manifest_imgs[str(xml_file.name)] = []
                    for line in old_f.readlines():
                        # look for a question ID before question/answer choice text
                        img_id_m = img_id_re.search(line)
                        if img_id_m:
                            img_id = img_id_m.group(1)
                            img_subid = 0
                            print("question: "+img_id)
                        # if this line contains question/answer text, process it.
                        question_text_m = question_text_re.search(line)
                        if question_text_m and img_id != "":
                            img_subid += 1
                            question_text = question_text_m.group(1)
                            #print(question_text)
                            # adjust paths of image URLs so they will render properly from the local filesystem
                            # insert: grab the embedded image filenames to delete later.
                            render_question_text=fix_special_chars(embedded_img_re.sub(embedded_img_sub,question_text))
                            # insert:  could process text further here
                            #    e.g. change names, swap question/completion, etc.
                            # make an image from the html of the question text (including images)
                            new_img_file = img_dir / PurePath("question_img_"+img_id+str(img_subid)+".jpg")
                            #print(new_img_file)
                            #print(render_question_text)
                            imgkit.from_string(render_head+render_question_text, new_img_file, config=config, options=options)
                            # insert: delete old image file(s)
                            # insert: hash under a different label for some export formats
                            manifest_imgs[str(xml_file.name)].append(new_img_file.relative_to(temp_zipdir).as_posix())
#                            new_question_text = '<img src="'+img_URL_prefix+str(new_img_file.relative_to(temp_zipdir).as_posix())+'" style="vertical-align: -5.0px;" />'
                            new_question_text = '<img src="'+img_URL_prefix+str(new_img_file.relative_to(temp_zipdir).as_posix())+'" />'
                            #print(new_question_text)
                            #print()
                            line=line.replace(question_text,new_question_text)
                        new_f.write(line)
            new_xml_file.replace(xml_file)
        print ("building manifest")
        #print(manifest_imgs)
        new_manifest_file = manifest_file.parent / Path('new_'+str(manifest_file.name))
        with open(manifest_file,'r', encoding='utf-8') as old_m:
            with open(new_manifest_file,'w') as new_m:
                for line in old_m.readlines():
                    new_m.write(line)
                    # if this line started the resource section for an xml file with images, write the image file refs here
                    if export_format == TESTGEN_SAKAI or export_format == SAKAI:
                        resource_m = re.search('<file .*?href="(.+\.xml)"',line)
                        if resource_m:
                            xml_file = resource_m.group(1)
                            #print("found reference to "+ xml_file)
                            for img_file in manifest_imgs[xml_file]:
                                manifest_line = '\t\t\t<file href="/'+str(img_file)+'"></file>\n'
                                new_m.write(manifest_line)
                            del manifest_imgs[xml_file]
                        # insert: remove references to old image files
        if manifest_imgs:
            print("images didn't get written to the manifest, aborting.")
        else:
            new_manifest_file.replace(manifest_file)
    new_zipfilename = str(zipfilename.parents[1] / processed_dir / zipfilename.stem)+'-text_to_img'+str(zipfilename.suffix)
    with ZipFile(new_zipfilename,'w') as new_zipobj:
        for each_file in temp_zipdir.rglob('*'):
            new_zipobj.write(each_file,arcname=each_file.relative_to(temp_zipdir),compress_type=compress_type)
    zipfilename.replace(zipfilename.parents[1] / queue_completed_dir / zipfilename.name)
    shutil.rmtree(temp_zipdir)
    print("created: " + new_zipfilename)
                        
print()
print("processing complete.")


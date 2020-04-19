# question_text_to_img

# What it does
Reads an xml assessment in zip file format, renders question/answer text html into images (including embedded figures), and creates a new xml assessment zip file with images replacing the text.  The intention is to prevent cutting-and-pasting text into a search engine during a timed assessment.

# Limitations
Works on exports from Pearson testgen in sakai format, or exports from tracs (sakai) in the "content packaging" format.
I'm working on getting the canvas formats functional.

Currently, the export format is identified by how it stores attached files (jpg,png,gif,pdf) so you must have at least one image or attachment included in the assessment export (an image in a question, a pdf attachment to a part, or a pdf attachment to the whole assessment, etc.)

# Installation, configuration, and usage
Requires the basic python installation (cpython) from http://python.org/
(Anaconda won't work, it doesn't support one of the modules needed.  I haven't tested other python distros.)

You need to install wkhtmltopdf from https://wkhtmltopdf.org/

On line 10 of the script you may need to manually put in the path to the location of the wkhtmltopdf executable.  If you are on Windows and you install wkhtmltopdf to the default location, it will probably just work without modification.

Python modules to install (via pip):
imgkit
pathlib
wcmatch

In the directory where you run the python script, make a directory called "queue" and put your zip files there.
after you run the script, any successfully processed files will be moved (unmodified) to "queue_completed", and the new files (with all text converted to images) will be created in "processed".

You may wish to edit the width of the rendered images.  I chose 350 to fit on phone screens.  If you want to change it, it's on line 14 of the script.

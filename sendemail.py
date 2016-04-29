import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Check for user imports
# if conflocal.py is not found, import default conf.py
try:
        import conflocal as conf
except ImportError:
        import conf


def sendEmail(source, message, subject, toaddress, fromaddress, filename):
    """Form and send email."""
    msg = MIMEMultipart()  # Create the container (outer) email message.
    msg['Subject'] = subject
    msg['From'] = fromaddress
    msg['To'] = toaddress
    mainbody = MIMEText(message, 'plain')
    msg.attach(mainbody)

    # Assume we know that the image files are all in PNG format
    # Open the files in binary mode.  Let the MIMEImage class automatically
    # guess the specific image type.
    if (filename != ""):
        fp = open(filename, 'rb')
        img = MIMEImage(fp.read())
        fp.close()
        msg.attach(img)

        # Send the email via our own SMTP server.
    try:
        # open up a line with the server
        s = smtplib.SMTP(conf.SMTPSERVER, conf.SMTPPORT)
        s.ehlo()
        s.starttls()
        s.ehlo()

        # login, send email, logout
        s.login(conf.mailUser, conf.mailPassword)
        s.sendmail(conf.mailUser, toaddress, msg.as_string())
        # s.close()
        s.quit()
    except:
        print("sendmail exception raised")
        return 0

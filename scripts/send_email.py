import smtplib, ssl

port = 25  # Local smtp server
smtp_server = "localhost"
sender_email = "mike@webtide.co.za"
receiver_email = "mike@metcalfe.co.za"
message = """\
Subject: Hi there

This message is sent from Python."""

context = ssl.create_default_context()
with smtplib.SMTP(smtp_server, port) as server:
    server.sendmail(sender_email, receiver_email, message)

# TODO: implement Python's logging capabilities
# TODO: integrate with configuration settings from matcher_app.py


# Logging helpers

def log_error(url):
    error_time = str(datetime.now())
    report = "=============ERROR=============\n"
    report += "TIME: " + error_time + "\n"
    report += "URL: " + url + "\n"
    report += "ERROR CLASS: " + str(sys.exc_info()[0]) + "\n"
    report += traceback.format_exc()
    report += "-------------------------------\n"
    with open('matcher_errors.log', 'a') as log_file:
        log_file.write(report)

There are 4 scripts on importance:

1. get_email.py
This is part of the sync process that is used to extract the files from emails. It is invoked from the cron job (sudo crontab -e) twice with different parameters, first to get the attached files and copy them into the "all" folder and second to extract them into the current folder and move the email to deleted email folder.

2. check_for_logs.py
Also part of the sync process called from the crobjob after the sync is complete, it will email administrators if the sync did not run that days by checking if a log files exists with that date ion the title.

3. rerun_files.py
This is a test/maintenace script that will copy/move the data files for a specified date from the "all" folder to the "current" folder. Once copied you can invoke the sync browserview function from the browser with get_emails=false (https://lims.hydrochem.com.au/@@sync_locations_view?get_emails=false)

4. rerun_from.py
Also a test/maintenace script the uses the rerun_files.py script to walk through the date range proved paramters to copy files and invoke the sync browserview function

The other scripts are test only scipts.

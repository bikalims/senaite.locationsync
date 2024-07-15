import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('test')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh = logging.FileHandler('/home/senaite/sync/logs/emails.log')
fh.setFormatter(formatter)
# fh.setLevel(level=logging.INFO)
logger.addHandler(fh)
# import pdb; pdb.set_trace()
logger.info('Info')


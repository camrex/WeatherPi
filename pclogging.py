#
#
# logging system from Project Curacao 
# filename: pclogger.py
# Version 1.0 10/04/13
#
# contains logging data 
#

CRITICAL=50
ERROR=40
WARNING=30
INFO=20
DEBUG=10
NOTSET=0

import sys
import time
import MySQLdb as mdb

# Check for user imports
try:
   import conflocal as conf
except ImportError:
   import conf

def log(level, source, message):

   LOWESTDEBUG = 0
	# open mysql database
	# write log
	# commit
	# close

   con = None
   cur = None

   if (level >= LOWESTDEBUG):
        try:
                #print("trying database")
                con = mdb.connect(conf.DATABASEHOST, conf.DATABASEUSER, conf.DATABASEPASSWORD, conf.DATABASENAME);
                cur = con.cursor()
                #print "before query"
                query = "INSERT INTO systemlog(TimeStamp, Level, Source, Message) VALUES(UTC_TIMESTAMP(), %i, '%s', '%s')" % (level, source, message)
	        #print("query=%s" % query)
                cur.execute(query)
                con.commit()
        except mdb.Error, e:
                print "Error %d: %s" % (e.args[0],e.args[1])
                if con is not None: con.rollback()
                #sys.exit(1)
        finally:
                if cur is not None: cur.close()
                if con is not None: con.close()
                del cur
                del con


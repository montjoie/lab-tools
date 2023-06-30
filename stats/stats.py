#!/usr/bin/env python3

import datetime
from datetime import timedelta
from datetime import datetime
import os
import time
import re
from six import iteritems
import subprocess
import xmlrpc.client
import sys
import yaml
import json
import argparse
import operator
import sqlite3
import xml

conn = sqlite3.connect('lava.db')

c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS stat
             (jobid text, end date, error_msg text, actual_device_id text, health text NOT NULL, state text NOT NULL, submitter text NOT NULL, waittime int, device_type text)''')

c.execute('CREATE UNIQUE INDEX IF NOT EXISTS index_name ON stat(jobid)')


def check_job(job):
        jobid = job["id"]
        if job["health"] == "Canceled":
            print("DEBUG: SKIP canceled %s" % jobid)
            return 0
        if job["health"] == "Unknown":
            print("DEBUG: SKIP Unknown %s" % jobid)
            return 0
        if job["health"] != "Complete" and job["health"] != "Incomplete":
            print("DEBUG: SKIP %s due to %s" % (jobid, job["health"]))
            return 0
        req = "SELECT * from stat WHERE jobid = %s" % jobid
        res = c.execute(req)
        sqle = res.fetchone()
        if sqle is not None:
            print("DEBUG: SKIP already done %s" % jobid)
            #print(sqle)
            return 0

        job_detail = server.scheduler.job_details(jobid)
        if job_detail["end_time"].value == None:
            print("DEBUG: SKIP no end %s" % jobid)
            return 0
        if job_detail["start_time"] is None:
            print("DEBUG: SKIP no start %s" % jobid)
            return 0
        if job_detail["start_time"].value == None:
            print("DEBUG: SKIP no start %s" % jobid)
            return 0
        if job_detail["end_time"].value is None:
            print("DEBUG: SKIP no end %s" % jobid)
            return 0
        job_submit = datetime.strptime(str(job_detail["submit_time"]), "%Y%m%dT%H:%M:%S")
        job_start = datetime.strptime(str(job_detail["start_time"]), "%Y%m%dT%H:%M:%S")
        diff = job_start - job_submit
        error_msg = None
        error_type = None
        if "error_msg" in job:
            error_msg = job["error_msg"]
        if "error_type" in job:
            error_type = job["error_type"]
        if error_msg is not None:
            if re.search('PRNG not seeded', error_msg):
                error_msg = 'Internal LAVA-docker dev deleted'
            elif re.search('Kernel panic \- not ', error_msg):
                error_msg = "Kernel panic"
            elif re.search('Connection reset by peer', error_msg):
                error_msg = "Connection reset by peer"
            else:
                error_msg = re.sub("[0-9]* seconds", 'XXX seconds', error_msg)
                error_msg = re.sub("[0-9]* bytes", 'XXX bytes', error_msg)
                error_msg = re.sub("storage.kernelci.org/images/rootfs/buildroot/.*rootfs", 'storage.kernelci.org/XXX/rootfs', error_msg)
                error_msg = re.sub("Invalid job data: \[\"Resource unavailable at.*Temporary failure in name resolution.*", 'Invalid job data: Temporary failure in name resolution',error_msg)
                error_msg = re.sub("Invalid job data: \[\"Unable to get.*Temporary failure in name resolution.*", 'Invalid job data: Temporary failure in name resolution',error_msg)
                error_msg = re.sub("Invalid job data: \[\"Resource unavailable at.*404.*", 'Invalid job data: 404',error_msg)
                error_msg = re.sub("Invalid job data: \[\"Resource unavailable at.*503.*", 'Invalid job data: 503',error_msg)
                error_msg = re.sub("Invalid job data: \[\"Unable to get.*503.*", 'Invalid job data: 503',error_msg)
                error_msg = re.sub("Invalid job data: \[\"Unable to get.*Name or service not known.*", 'Invalid job data: Name or service not known',error_msg)
        c.execute('INSERT INTO stat VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                    str(jobid),
                    datetime.strptime(job_detail['end_time'].value, '%Y%m%dT%H:%M:%S'),
                    error_msg,
                    job_detail['actual_device_id'],
                    job['health'],
                    job['state'],
                    job['submitter'],
                    diff.seconds,
                    job['device_type'],
                    error_type)
                    )

def genlist(server, offset, smax, emsg):
    print("GENLIST %d max=%d" % (offset, smax))
    try:
        jlist = server.scheduler.jobs.list('FINISHED', None, offset, smax, None, emsg)
    except xmlrpc.client.Fault as e:
        if e.faultCode == 404:
            print("ERROR: 404")
            return 1
        else:
            print(e)
            return 2
    except xmlrpc.client.ProtocolError:
        print("ERROR: xmlrpc.client.ProtocolError")
        return 2
    except xml.parsers.expat.ExpatError:
        print("XML ERROR")
        return 3
    print("DEBUG: analyze joblist")
    number = 0
    for job in jlist:
        check_job(job)
        number = number + 1
    if smax > 1 and number < smax:
        print("END %d" % number)
        return 1
    print("NEXT")
    return 0

parser = argparse.ArgumentParser()
parser.add_argument("--noact", "-n", help="No act", action="store_true")
parser.add_argument("--old", help="No act", action="store_true")
parser.add_argument("--quiet", "-q", help="Quiet, do not print build log", action="store_true")
parser.add_argument("--gen", help="", type=int, default=100)
parser.add_argument("--offset", help="", type=int, default=0)
parser.add_argument("--start", help="", type=int, default=0)
parser.add_argument("--end", help="", type=int, default=2196314)
args = parser.parse_args()

if args.old:
    ecount = 0
    jmax = 100
    idx = args.offset
    ret = 0
    if idx < args.gen:
        server = xmlrpc.client.ServerProxy(os.environ.get("LAVAURI"), allow_none=True)
    while ret == 0 and idx < args.gen:
        ret = genlist(server, idx, jmax, True)
        if ret == 0:
            idx = idx + jmax
        if ret == 2:
            print("RETRY")
            jmax = 1
            ret = 0
            ecount += 1
            if ecount == 10:
                jlist = server.scheduler.jobs.list('FINISHED', None, idx - 10, 10, None, True)
                print(jlist)
                sys.exit(0)
        # retry one by one
        if ret == 3:
            for idxx in range(idx, idx + jmax):
                print("RETRY %d" % idxx)
                rret = genlist(server, idxx, 1, True)
                if rret == 3:
                    rret = genlist(server, idxx, 1, False)
            idx = idx + jmax
            ret = 0
    conn.commit()
else:
    server = xmlrpc.client.ServerProxy(os.environ.get("LAVAURI"), allow_none=True)
    jn = args.start
    if jn == 0:
        print("CANNOT start at 0")
        sys.exit(1)
    while jn < args.end:
        try:
            job = server.scheduler.jobs.show(jn)
        except xmlrpc.client.Fault as e:
            if e.faultCode == 404:
                print("DEBUG: %s not found" % jn)
                jn += 1
                continue
            sys.exit(1)
        check_job(job)
        jn += 1
        print(jn)
    conn.commit()


print("GEN STATS")

########### fiabi by device by day
fdd = {}
req = "select distinct actual_device_id from stat"
req = "select health,actual_device_id,strftime('%Y/%m/%d', `end`),error_msg FROM stat WHERE submitter == 'lava-health' AND end BETWEEN DATE('now', '-40 day') and DATE('now') ORDER BY date(end)"
res = c.execute(req)
toto = res
for row in toto:
    date = row[2]
    dt = row[1]
    h = row[0]
    print("%s %s %s %s" % (row[0], row[1], row[2], row[3]) )
    if dt not in fdd:
        fdd[dt] = {}
    if date not in fdd[dt]:
        fdd[dt][date] = {}
        fdd[dt][date]["total"] = 0
        fdd[dt][date]["bad"] = 0
        fdd[dt][date]["badok"] = 0
    if h == "Incomplete":
        fdd[dt][date]["total"] += 1
        if row[3] != None and (re.search("matched a bootloader error message: 'Retry count exceeded'", row[3])
            or re.search("matched a bootloader error message: 'Retry time exceeded", row[3])
            or re.search("matched a bootloader error message: 'TIMEOUT'", row[3])):
            fdd[dt][date]["badok"] += 1
            print("DEBUG ok\n")
        else:
            fdd[dt][date]["bad"] += 1
    if h == "Complete":
        fdd[dt][date]["total"] += 1
for dt in fdd:
    dhc = open("hc/%s" % dt, "w")
    for date in fdd[dt]:
        # HACK increase bad with badok for viewing it
        dhc.write("%s %d %d %d\n" % (date, fdd[dt][date]["total"], fdd[dt][date]["bad"] + fdd[dt][date]["badok"], fdd[dt][date]["badok"]))
        #dhc.write(str(date))
    dhc.close()

###########

for inter in [30, 15, 7, 2, 1]:
    req = "select device_type, AVG(waittime) FROM stat WHERE end BETWEEN DATE('now', '-%d day') and DATE('now') GROUP BY device_type ORDER BY AVG(waittime) DESC" % inter
    print(req)
    res = c.execute(req)
    fwait = open("waittime-%d.dat" % inter, 'w')
    for row in res:
        print(row)
        #print("%s %f" % (board, wt[board]))
        fwait.write("%s %f\n" % (row[0], row[1]))
    fwait.close()

req = "select count(*),strftime('%d/%m/%Y', `end`) FROM stat GROUP BY strftime('%d/%m/%Y', `end`) ORDER BY date(end)"
res = c.execute(req)
fwait = open("statbyday.dat", 'w')
for row in res:
    print(row)
    fwait.write("%s %s\n" % (row[1], row[0]))
fwait.close()

#select end,device_type FROM stat WHERE end BETWEEN DATE('now', '-4 day') and DATE('now');

stat = {}
userlist = []
errors = {}

req = "select count(*), actual_device_id, submitter, health FROM stat GROUP BY actual_device_id, submitter, health"
res = c.execute(req)
for row in res:
    print(row)
    devid = row[1]
    if devid not in stat:
        stat[devid] = {}
        stat[devid]["health"] = {}
        stat[devid]["uboot"] = "TODO"
    user = row[2]
    if user not in userlist:
        userlist.append(user)
    if user not in stat[devid]:
        stat[devid][user]= {}
        stat[devid][user]["total_jobs"] = 0
        stat[devid][user]["fail"] = 0
        stat[devid][user]["other"] = 0
        stat[devid][user]["week"] = {}
        stat[devid][user]["week"]["total"] = 0
        stat[devid][user]["week"]["fail"] = 0
        stat[devid][user]["week"]["other"] = 0
        stat[devid][user]["month"] = {}
        stat[devid][user]["month"]["total"] = 0
        stat[devid][user]["month"]["fail"] = 0
        stat[devid][user]["month"]["other"] = 0
    stat[devid][user]["total_jobs"] = stat[devid][user]["total_jobs"] + row[0]
    if row[3] == 'Incomplete':
        stat[devid][user]["fail"] = stat[devid][user]["fail"] + row[0]

req = "select count(*), actual_device_id, error_msg FROM stat WHERE end BETWEEN DATE('now', '-20 day') and DATE('now') and error_msg IS NOT NULL GROUP BY actual_device_id, error_msg ORDER BY count(*) ASC"
res = c.execute(req)
for row in res:
    print(row)
    devid = row[1]
    emsg = row[2]
    if emsg not in errors:
        errors[emsg] = {}
        errors[emsg]["total"] = 0
    errors[emsg]["total"] = errors[emsg]["total"] + row[0]
    errors[emsg][devid] = {}
    errors[emsg][devid]["total"] = row[0]
    errors[emsg][devid]["days"] = {}

req = "select count(*), actual_device_id FROM stat WHERE submitter == 'lava-health' and health == 'Incomplete' GROUP BY actual_device_id"
req = "select actual_device_id, 100 * count(*) / (SELECT count(*) FROM stat a where a.actual_device_id == b.actual_device_id and submitter == 'lava-health') FROM stat b WHERE submitter == 'lava-health' and health == 'Incomplete' GROUP BY actual_device_id ORDER BY 100 * count(*) / (SELECT count(*) FROM stat a where a.actual_device_id == b.actual_device_id and submitter == 'lava-health')"
res = c.execute(req)
inter = 30
fiabi = open("fiabi-%d.dat" % inter, 'w')
for row in res:
    print(row)
    fiabi.write("%s %s\n" % (row[0], row[1]))
fiabi.close()

print(userlist)


ws = open("/var/www/html/lava/index.html", 'w')
ws.write("<html><head><link rel=stylesheet href=lava.css type=text/css /></head><body>\n")
ws.write("<table>\n")
ws.write("<tr>\n")
ws.write("<td>Board name</td>\n")
ws.write("<td>uboot</td>\n")
for user in userlist:
    ws.write("<td colspan=9>%s</td>\n" % user)
ws.write("</tr>\n")

ws.write("<tr>\n")
ws.write("<td></td>\n")
ws.write("<td></td>\n")
for user in userlist:
    ws.write("<td colspan=3>Total</td>\n")
    ws.write("<td colspan=3>Month</td>\n")
    ws.write("<td colspan=3>Week</td>\n")
ws.write("<td></td>\n")
ws.write("</tr>\n")

ws.write("<tr>\n")
ws.write("<td></td>\n")
ws.write("<td></td>\n")

for user in userlist:
    ws.write("<td>Total</td>\n")
    ws.write("<td>Failed</td>\n")
    ws.write("<td>Other</td>\n")
    ws.write("<td>Total</td>\n")
    ws.write("<td>Failed</td>\n")
    ws.write("<td>Other</td>\n")
    ws.write("<td>Total</td>\n")
    ws.write("<td>Failed</td>\n")
    ws.write("<td>Other</td>\n")
ws.write("</tr>\n")

for board in stat:
    ws.write("<tr>\n")
    ws.write("<td>%s</td>\n" % board)
    ws.write("<td>%s</td>\n" % stat[board]["uboot"])

    for user in userlist:
        if user not in stat[board]:
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            ws.write("<td></td>\n")
            continue
        ws.write("<td>%d</td>\n" % stat[board][user]["total_jobs"])
        color = "green"
        if stat[board][user]["fail"] > 0:
            color = "red"
        ws.write('<td class="%s">%d</td>\n' % (color, stat[board][user]["fail"]))
        ws.write('<td>%d</td>\n' % stat[board][user]["other"])

        ws.write("<td>%d</td>\n" % stat[board][user]["month"]["total"])
        color = "green"
        if stat[board][user]["month"]["fail"] > 0:
            color = "red"
        ws.write('<td class="%s">%d</td>\n' % (color, stat[board][user]["month"]["fail"]))
        ws.write('<td>%d</td>\n' % stat[board][user]["month"]["other"])

        ws.write("<td>%d</td>\n" % stat[board][user]["week"]["total"])
        color = "green"
        if stat[board][user]["week"]["fail"] > 0:
            color = "red"
        ws.write('<td class="%s">%d</td>\n' % (color, stat[board][user]["week"]["fail"]))
        ws.write('<td>%d</td>\n' % stat[board][user]["week"]["other"])

    ws.write("</tr>\n")
ws.write("</table>\n")

ws.write("<table>\n")
for emsg in errors:
    ws.write("<tr>\n")
    ndevs = len(errors[emsg]) - 1
    ws.write("<td rowspan=%d>%s</td>\n" % (ndevs, emsg))
    ws.write("<td rowspan=%d>%d</td>\n" % (ndevs, errors[emsg]["total"]))
    n = 0
    for devid in errors[emsg]:
        if devid == "total":
            continue
        if n > 0:
            ws.write("<tr>\n")
        ws.write("<td>%s</td><td>%d</td>" % (devid, errors[emsg][devid]["total"]))
        day = 0
        while day < 15:
            if day in errors[emsg][devid]["days"]:
                ws.write("<td>%d</td>" % errors[emsg][devid]["days"][day])
            else:
                ws.write("<td></td>\n")
            day = day + 1
        ws.write("</tr>\n")
        n = n + 1

ws.write("</table>\n")

for inter in [30, 15, 7, 2, 1]:
    ws.write("<img src='waittime-%d.png'>\n" % inter)
ws.write("<img src='statbyday.png'>\n")
ws.write("<img src='fiabi.png'>\n")
ws.write("</body></html>\n")
ws.close()
conn.close()

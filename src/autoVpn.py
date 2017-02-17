# -*- coding: utf-8 -*-
'''
Created on 2016年12月4日

@author: luoz
'''

from threading import Thread 
import subprocess 
from Queue import Queue 
import time 
import sys,os
import platform 
testIp = "8.8.8.8"
gVpnList = ["ps4hk1.8lag.net",
            "ps4hk2.8lag.net",
            "ps4hk3.8lag.net",
            "ps4hk4.8lag.net",
            "ps4hk5.8lag.net",
            "ps4hk6.8lag.net",
            "ps4hk7.8lag.net",
            "hdbf1jp1.8lag.net",
            "hdbf1jp2.8lag.net",
            "hdbf1jp3.8lag.net",
            "hdbf1jp4.8lag.net",
            "hdbf1jp5.8lag.net",
            "hdbf1jp6.8lag.net"]

def pingParserAvgTime(cmd,strRet):
    if platform.system() == "Linux": 
        for line in strRet.split("\n"):
            line = line.strip()
            if(line.startswith("rtt min/avg/max/mdev")):
                strAvg = line.split("/")[4]
                return float(strAvg)
    elif platform.system() == "Windows": 
        avgMsStr = strRet.split()[-1]
        if(avgMsStr.endswith("ms")):
            strAvg=avgMsStr[0:-2]
            if(strAvg.isdigit()):
                return int(strAvg)
    print("[WARN]pingParserAvgTime,[%s] result not support"%(" ".join(cmd)))    
    return 65535

gHostTestResult={}
queue = Queue() 
maxTestCount = 5        
import traceback    
def cmdExe(cmd,rsltCheckHandle=None,errorRslt=False,succRslt=True):
    try:
        print("[CMD]"+" ".join(cmd))
        if platform.system() == "Linux": 
            cmdOutput = subprocess.check_output(cmd,shell=False)
        elif platform.system() == "Windows": 
            cmdOutput = subprocess.check_output(cmd,shell=True)
        if(rsltCheckHandle != None):
            return rsltCheckHandle(cmd,cmdOutput)
        else:
            return succRslt
    except:
        #print("cmdExe:[%s] exception"%" ".join(cmd))  
        #traceback.print_exc()  
        return errorRslt
def cmdExeNotRslt(cmd):
    print("[CMD]"+cmd)
    os.system(cmd+" 1>/dev/null 2>/dev/null")
    #os.system(cmd)
def pinger(i,q): 
    while True: 
        ip = q.get() 
        if platform.system() == "Linux": 
            cmd = ["ping","-c",str(maxTestCount),ip] 
        elif platform.system() == "Windows": 
            cmd = ["ping","-n",str(maxTestCount),ip] 
        gHostTestResult[ip]=cmdExe(cmd,pingParserAvgTime,65535)
        q.task_done() 
        
def remoteHostTest(hostList):
    time.sleep(1)      
    gHostTestResult.clear()
    for ip in hostList: 
        queue.put(ip) 
        print("[INFO]remote host check:%s\n"%ip)
    queue.join() 
    sortHost = sorted(gHostTestResult.iteritems(), key=lambda d:d[1], reverse = False)
    availableVpns = []
    for (ip,avgTime) in sortHost:
        print("[INFO]ip:%s,avgTime:%s"%(ip,avgTime))
        if(avgTime != 65535):
            availableVpns.append((ip,avgTime))
    return availableVpns
def getVpnName(vpnIp):
    return vpnIp.split(".")[0]

def getVpnIp(vpnName):
    for vpnIp in gVpnList:
        if (vpnName == getVpnName(vpnIp)):
            return vpnIp
    return None
def vpnCreate(vpnIp,username,passwd):
    cmdExe(["pptpsetup" "--create", getVpnName(vpnIp),"--server",vpnIp,"--username" ,username,"--password",passwd, "--encrypt"])
def ifconfigParser(cmd,rsltStr):
    isFind = False
    for line in rsltStr.split("\n"):
        line = line.strip()
        if(line.startswith("ppp0")):
            isFind = True
        elif(line.startswith("inet addr:") and isFind):
            index = line.find("P-t-P:")
            if(index <0):

                return None
            remoteGate = line[index+len("P-t-P:"):].split()[0]
            print("[INFO]ifconfigParser,[%s] find gate,%s"%(" ".join(cmd),remoteGate))
            return remoteGate
    #print("ifconfigParser:[%s],not support rslt"%(" ".join(cmd)))
    return None

def vpnConn(vpnIp):
    cmdExeNotRslt("poff")
    time.sleep(1)
    if(not cmdExe(["pppd","call", getVpnName(vpnIp)])):
        return
    remoteGate = None
    for loop in range(10):
        time.sleep(2)
        remoteGate = cmdExe(["ifconfig"],ifconfigParser,None)
        if(remoteGate != None):
            break
    if(remoteGate == None):
        print("[WARN]vpnConn,get gate fail,vpn connect fail")
        return 65535
    cmdExeNotRslt("iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE")
    cmdExeNotRslt("iptables -t nat -A POSTROUTING -o ppp0 -j MASQUERADE")
    cmdExeNotRslt("ip route del dev eth0")
    cmdExeNotRslt("ip route del dev ppp0")
    cmdExeNotRslt("ip route add via %s dev ppp0"%(remoteGate))
    
    testHost=remoteHostTest([testIp])
    if(len(testHost) == 0):
        return 65535
    return testHost[0][1]

def vpnAutoConn(vpnIps):
    vpnRslt = {}
    for (vpnIp,avgTimeMs) in vpnIps:
        time.sleep(1)
        testTime = vpnConn(vpnIp)
        print("[INFO]vpn Test:vpn=%s,testHost=%s,time=%s"%(vpnIp,testIp,testTime))
        if(testTime == 65535):
            continue
        vpnRslt[vpnIp] = vpnConn(vpnIp)
    
    sortHosts = sorted(vpnRslt.iteritems(), key=lambda d:d[1], reverse = False)
    
    for vpnIp,avgTime in sortHosts:
        time.sleep(1)
        print("[INFO]select vpn=%s,avgTime=%s"%(vpnIp,avgTime))
        testTime = vpnConn(vpnIp)
        if(testTime !=65535):
            print("[INFO]select vpn success,[vpn=%s],testHost=%s,time=%s"%(vpnIp,testIp,testTime))
            return
        else:
            print("[WARN]select vpn fail,[vpn=%s],testHost=%s,time=%s"%(vpnIp,testIp,testTime))
            
def vpnActive():
    remoteGate = cmdExe(["ifconfig"],ifconfigParser,None)
    return remoteGate != None
def autoKeepVpn(vpnList):
    print("[INFO]auto keep vpn start:")
    cmdExeNotRslt("poff")
    time.sleep(1)
    while True:
        print time.strftime("[INFO]%Y-%m-%d %H:%M %p", time.localtime())
        if(not vpnActive()):
            availableVpns=remoteHostTest(vpnList)
            vpnAutoConn(availableVpns)
        time.sleep(30)
def autoConnVpn(vpnList):
    print("[INFO]auto select vpn start:")
    cmdExeNotRslt("poff")
    time.sleep(1)
    availableVpns=remoteHostTest(gVpnList)
    vpnAutoConn(availableVpns)
def connSelectVpn(vpnName):
    cmdExeNotRslt("poff")
    time.sleep(1)
    vpnIp = getVpnIp(vpnName)
    if(vpnIp == None):
        print("[ERROR]vpn is not found:%s"%(vpnName))
    else:
        testTime = vpnConn(vpnName)
        print("[INFO]vpn=%s,testHost=%s,time=%s"%(vpnIp,testIp,testTime))
if __name__ == '__main__':
    num_threads = len(gVpnList) 
    for i in range(num_threads): 
        worker = Thread(target=pinger, args=(i, queue)) 
        worker.setDaemon(True) 
        worker.start()         
    if(len(sys.argv)>1):
        if(sys.argv[1] == "-a"):
            autoConnVpn(gVpnList)
        if(sys.argv[1] == "-k"):
            autoKeepVpn(gVpnList)
        if(sys.argv[1] == "-n"):
            vpnName = sys.argv[2].strip()
            connSelectVpn(vpnName)
    else:
        availableVpns=remoteHostTest(gVpnList)
        

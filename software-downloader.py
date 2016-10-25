#!/usr/bin/env python

#Copyright (c) 2016 Data Equipment AS
#Author: Tor Mogstad <torm _AT_ dataequipment.no>

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.




"""Text menu based script for downloading software updates from
support.paloaltonetworks.com
"""

from contentdownloader import LoginError
from contentdownloader import UpdateError
from contentdownloader import UnknownPackage
from contentdownloader import ContentDownloader
import sys
import os
import re
import json
from os import path
import argparse
import logging
import traceback
import ConfigParser


##### Static variables used in script - change only if needed
CONFIG_FILE = "config.conf"  # Config file
DATA_CACHE_FILE = "pan_releases_cache.json"
LOG_FILE = "log.txt"  # Log file used by script
# Supported loglevels
LOGLEVELS = {
		"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
}

# Readable list
READABLE_FORMAT = {
	"PanOS_200": "PAN-OS for PA-200",
	"PanOS_500": "PAN-OS for PA-500",
	"PanOS_2000": "PAN-OS for PA-2000",
	"PanOS_3000": "PAN-OS for PA-3000",
	"PanOS_5000": "PAN-OS for PA-5000",
	"PanOS_7000": "PAN-OS for PA-7000",
	"PA-VM-ESX": "PAN-OS for VM-Series Base Image",
	"Phoenix": "PAN-OS for VM-Series Base Image",
	"PA-VM": "PAN-OS for VM-Series Base Image",
	"PanOS_vm": "PAN-OS for VM-Series",
	"PanCMS_pc": "PAN-OS for VM-Series",
	"PA-VM-NSX": "PAN-OS for VM-Series NSX Base Images",
	"PA-VM-SDX": "PAN-OS for VM-Series SDX Base Images",
	"PA-VM-KVM": "PAN-OS for VM-Series KVM Base Images",
	"PA-VM-HPV": "PAN-OS for VM-Series Hyper-V Base Images",
	"PanGP": "GlobalProtect Agent Bundle",
	"PanVPN": "NetConnect Agent Bundle",
	"Panorama_pc": "Panorama Updates",
	"Panorama-ESX": "Panorama Base Images",
	"Panorama-Server": "Panorama Base Images",
	"Panorama_m": "Panorama M Images",
	"WildFire_m": "WF-500 Appliance Updates",
	"ESMCore_x64": "Endpoint Security Manager - Core",
	"ESMConsole_x64": "Endpoint Security Manager - Console",
	"ClientUpgradePackage": "Endpoint Protection for workstations - Upgrade packages",
	"Traps_x64": "Endpoint Protection for workstations - x64",
	"Traps_x86": "Endpoint Protection for workstations - x86",
	"TrapsVDITool_x64": "Endpoint Protection for virtual desktop infrastructure VDI Tool - x64",
	"TrapsVDITool_x86": "Endpoint Protection for virtual desktop infrastructure VDI Tool - x86",
	"TrapsVDIToolx64": "Endpoint Protection for virtual desktop infrastructure VDI Tool - x64",
	"TrapsVDIToolx86": "Endpoint Protection for virtual desktop infrastructure VDI Tool - x86",
	"Traps_VDI_x64": "Endpoint Protection for virtual desktop infrastructure VDI - x64",
	"Traps_VDI_x86": "Endpoint Protection for virtual desktop infrastructure VDI - x86",
	"Traps_Server_x64": "Endpoint Protection for servers - x64",
	"Traps_Server_x86": "Endpoint Protection for servers - x86",
	"Traps_server_x64": "Endpoint Protection for servers - x64",
	"Traps_server_x86": "Endpoint Protection for servers - x86",
	"UaInstall": "User ID Agent",
	"PanAgent": "User ID Agent",
	"LaInstall": "User ID LDAP Agent",
	"TaInstall64.x64": "Terminal Service Agent - x64",
	"TaInstall64": "Terminal Service Agent - x64",
	"TaInstall": "Terminal Service Agent - Win32",
	"TaInstall32": "Terminal Service Agent - Win32",
	"GlobalProtect": "Global Protect Agent - Win32",
	"GlobalProtect64": "Global Protect Agent - x64",
	}


def get_passed_arguments():
    parser = argparse.ArgumentParser(description='''Text menu based script for download updates from support.paloaltonetworks.com.
	 								config.conf file must exist in directory and have a valid username and password in it.
									''')
    parser.add_argument('-l', '--loglevel', help="Set loglevel. Options: DEBUG, INFO, WARNING, ERROR or CRITICAL. Defaults to INFO")
    return parser.parse_args()

def start_logging(args="loglevel"):
	global loglevel  # Need to change global loglevel variable
	# Setting log level and logfile
	if args is None:
		loglevel = "DEBUG"  # Default is INFO
	else:
		loglevel = args
	# If invalid loglevel passed by user.. exit..
	if loglevel not in LOGLEVELS:
		log_message = "Unknown loglevel type: %s" % args
		print log_message
		sys.exit()
	# Set logging.basicConfig based on loglevel
	try:
		if loglevel == "DEBUG":
			logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format='%(asctime)s - %(levelname)s -  %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
		elif loglevel == "INFO":
			logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
	        elif loglevel == "WARNING":
        	        logging.basicConfig(filename=LOG_FILE, level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
	        elif loglevel == "ERROR":
        	        logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
	        elif loglevel == "CRITICAL":
        	        logging.basicConfig(filename=LOG_FILE, level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
	except Exception as e:
		print "ERROR setting logging level"
		print(e)
		sys.exit(0)
	# Logging first message on script start
	logging.info("Script started, and logging to file initialized")

def get_config(filename):
    config = ConfigParser.SafeConfigParser({"filedir": ""})
    config.read(filename)
    username = config.get('config', 'username')
    password = config.get('config', 'password')
    download_dir = config.get('config', 'filedir')
    if download_dir == "":
        download_dir = os.getcwd()
    return username, password, download_dir

def generate_release_list(releases):
	complete_list = []
	for release in releases:
		version = release[0]
		link = release[1]
		if "WFWin" in version: continue #Skip these files
		if "pkg" in version: continue #Skip these files
		if "apk" in version: continue #Skip these files
		if "generic" in version: continue #Skip thises txt files
		try:
			#Find Release name
			name = re.sub(r'(-[0-9].*)', "", version) #Normal pan_os
			name = re.sub(r'(_[0-9]\.[0-9]\.[0-9].*)', "", name) #Some traps and gp versions
			name = re.sub(r'(_\.[0-9]\.[0-9]\.[0-9].*)', "", name) #other traps versions
			if name[-1] == "_": name = name[:-1] #remove trailing _ from gp and traps

			#Find release main version
			complete_version = re.findall(r'([0-9]\..*)', version)[0]
			main_version = "%s.%s" % (complete_version.split(".")[0], complete_version.split(".")[1])
		except:
			pass #link not what we are looking for, and can be ignored.
			complete_version = "Error"
			main_version = "Error main"
			name = "Name Error"
		#Find reable name - if defined
		if name in READABLE_FORMAT:
			readable_name = READABLE_FORMAT[name]
		else:
			readable_name = name
		this_release = [name, main_version, complete_version, link, readable_name]
		complete_list.append(this_release)

	#Store list in file
	with open(DATA_CACHE_FILE, 'wb') as outputfile:
		json.dump(complete_list, outputfile)

	return complete_list

def build_main_menu(release_list):
	quit_option = [0,"Quit"]
	refresh_option = [1,"Refresh release information from download.paloaltonetworks.com"]
	main_menu = [quit_option]
	main_menu.append(refresh_option)
	counter = 2
	for release in release_list:
		#check if item exists in menu_item
		exists = False
		for item in main_menu:
			if release[4] == item[1]: exists = True
		if not exists:
			menu_item = [counter, release[4]]
			main_menu.append(menu_item)
			counter += 1
	return main_menu

def generate_sub_menu_1(release_list, selected_modell):
	back_option = [0,"Back"]
	quit_option = [1,"Quit"]
	sub_menu_1 = [back_option]
	sub_menu_1.append(quit_option)
	counter = 2
	for release in release_list:
		#check if item has correct name
		if release[4] == selected_modell:
			#check if item exists in sub_menu_1
			exists = False
			for item in sub_menu_1:
				if item[1] == release[1]: exists = True
			if not exists:
				this_item = [counter,release[1]]
				sub_menu_1.append(this_item)
				counter += 1
	return sub_menu_1

def generate_sub_menu_2(release_list, selected_main, selected_modell):
	back_option = [0,"Back"]
	quit_option = [1,"Quit"]
	sub_menu_2 = [back_option]
	sub_menu_2.append(quit_option)
	counter = 2
	for release in release_list:
		#check if item has correct name
		if release[4] == selected_modell:
			if release[1] == selected_main:
				#check if item exists in sub_menu_1
				this_item = [counter,release[2],release[3]]
				sub_menu_2.append(this_item)
				counter += 1
	return sub_menu_2

def main():
	# Get passed arguments
	args = get_passed_arguments()
	# Start logging
	if args.loglevel:
		if args.loglevel in LOGLEVELS: start_logging(args.loglevel)
		else:
			log_message = "Unsupported log leve set %s. Exiting...." % (args.loglevel)
			logging.error(log_message)
			if verbose: print log_message
			sys.exit()
	else: start_logging("INFO")  # INFO is default

	#Parse config file
	username, password, download_dir = get_config('config.conf')

	#Create contentdownloader
	if args.loglevel == "DEBUG": debugenabled = True
	else: debugenabled = False
	SwDownloader = ContentDownloader(username=username, password=password, debug=debugenabled)

	#Try to open cache file
	try:
		with open(DATA_CACHE_FILE, 'r') as inputfile:
			release_list = json.load(inputfile)
		inputfile.close()
		print "\nRelease information succesfully retrieved from cache..."
	except: #Download content and generate new releash list if file doesn't exist
		print "\nUnable read or find cache file. Retrieving release information from downloads.paloaltonetworks.com..please wait"
		print "\nNB! account %s used to retrive files. You will only be able to download software accesible from this account." % (username)
		releases = SwDownloader.get_all_releases()
		release_list = generate_release_list(releases)

	#Initial menu
	while True:
		# Generate main meny table
		main_menu = build_main_menu(release_list)
		#Print menu and catch user selection
		print "\nDownload PAN-OS software from support.paloaltonetworks.com"
		print "Please select which device to download software for:\n"
		for option in main_menu:
			print "%s - %s" %(option[0], option[1])
		print ""
		choice = input("Selection: ")
		choice = int(choice)

		if choice == 0: sys.exit() #Quit menu item
		elif choice == 1: # Refresh menu item
			print "\nRetrieving release information from downloads.paloaltonetworks.com..please wait"
			print "NB! account %s used to retrive files. You will only be able to download software accesible from this account." % (username)
			releases = SwDownloader.get_all_releases()
			release_list = generate_release_list(releases)
		elif choice > len(main_menu)-1: print "Incorrect selection..please try again.."
		else:
			#Sub menu 1
			selected_modell = main_menu[choice][1]
			#Generate submenu
			sub_menu_1 = generate_sub_menu_1(release_list, selected_modell)
			#print main_releases
			while True:
				print "\nSelect PAN-OS main release:\n"
				for main_release in sub_menu_1:
					print "%s - %s" % (main_release[0], main_release[1])
				print ""
				choice_main_version = input("Selection: ")
				choice_main_version = int(choice_main_version)
				if choice_main_version == 0: break
				if choice_main_version == 1: sys.exit()
				if choice_main_version > len(sub_menu_1)-1: print "Incorrect selection..please try again.."
				else:
					selected_main = sub_menu_1[choice_main_version][1]

					#Generate submenu2
					sub_menu_2 = generate_sub_menu_2(release_list, selected_main, selected_modell)
					while True:
						print "\nAvailable releases for main release %s. Please select to download:\n" % (selected_main)
						for item in sub_menu_2:
							print "%s - %s" % (item[0], item[1])
						print ""
						choice_patch_version = input("Selection: ")
						choice_patch_version = int(choice_patch_version)
						if choice_patch_version == 0: break
						if choice_patch_version == 1: sys.exit()
						if choice_patch_version > len(sub_menu_2)-1: print "Incorrect selection..please try again.."
						else:
							download_release = sub_menu_2[choice_patch_version]
							print "\nDownloading %s for %s from %s....." % (download_release[1], selected_modell, download_release[2])
							SwDownloader.download_software(download_dir,download_release[2])
							print "\n%s has been downloaded to folder %s\n" % (download_release[1],download_dir)

if __name__ == '__main__':
	main()

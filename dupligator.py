import os,subprocess,hashlib

LEFTOFF:  I need to get multiprocessing working!  This will be too slow otherwise!

class FileInfo:
	# these file extensions will all be collapsed into the first entry
	EXTENSION_SYNONYMS=[['html','htm','xhtml'],['jpeg','jpg']]
	
	def __init__(self,path):	
		self.abspath=os.path.abspath(path)
		try:
			self._size=os.path.getsize(self.abspath)
		except:
			self._size=-1
		self._hash=None
		self._extension=None
		
	def size(self):
		return self._size
		
	def read(self):
		return open(self.abspath,'rb').read()
		
	def extension(self):
		"""
		returns the file extension or ''
		
		NOTE: this is smart and uses EXTENSION_SYNONYMS to convert
		like get 'html' extension from 'foo.htm'
		"""
		if self._extension==None:
			fname=self.abspath.rsplit(os.sep,1)[-1].rsplit('.',1)
			if len(fname)>1:
				self._extension=fname[-1].lower()
				for syn in self.EXTENSION_SYNONYMS:
					if self._extension in syn:
						self._extension=syn[0]
			else:
				self._extension=''
		return self._extension
		
	def short(self):
		"""
		short filename as in /foo/bar.htm => bar
		"""
		return self.abspath.rsplit(os.sep,1)[-1].rsplit('.',1)[0]
		if len(short)>1:
			extension=short[-1]
		else:
			extension=''
		short=short[0]
		
	def hash(self):
		if self._hash==None:
			self._hash=hashlib.md5(self.read()).hexdigest()
		return self._hash
		
	def __eq__(self,otherFile,bitwise=True):
		"""
		if bitwise, then will make sure both files are bit-for-bit compatible
		"""
		if otherFile==None or self._size==-1:
			return False
		if type(otherFile)==str or type(otherFile)==unicode:
			otherFile=FileInfo(otherFile)
		if otherFile.size()==self.size():
			if otherFile.hash()==self.hash():
				if bitwise:
					if self.read()==otherFile.read():
						return True
				else:
					return True
		return False
		
	def __str__(self):
		return self.abspath
	
		
class DupliGator:
	"""
	Finds and removes duplicate files
	"""
	
	def __init__(self):
		self._db={} # {extension:{short_filename:[FileInfo]}}
		self.dups=[]
	
	def _createLink(self,fromFile,toFile):
		if os.name=='winnt':
			cmd='mklink "'+fromFile+'" "'+toFile+'"'
		else:
			cmd='ln -s "'+fromFile+'" "'+toFile+'"'
		out,err=subprocess.popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
		err=err.strip()
		if err!=None:
			raise Exception(cmd+'\n'+err)
		
	def _remDup(self,originalFile,duplicateFile):
		os.remove(duplicateFile)
		self._createLink(duplicateFile,originalFile)
		
	def _hasDup(self,fileInfo,detectDifferentFilenames=True):
		"""
		if the file has a duplicate, return its FileInfo
		otherwise NONE
		
		fileInfo can be a FileInfo object or filename string
		
		detectDifferentFilenames will match files even if 
		the names have changed.  This is more thourough, but
		also slower.
		"""
		if type(fileInfo)==str or type(fileInfo)==unicode:
			fileInfo=FileInfo(fileInfo)
		if self._db.has_key(fileInfo.extension()):
			ext=self._db[fileInfo.extension()]
			if not detectDifferentFilenames:
				for m in ext[fileInfo.short()]:
					if m.abspath==fileInfo.abspath:
						pass # a file is not a duplicate of itsself
					elif m==fileInfo:
						return m
			else:
				for f in self._db[fileInfo.extension()].values():
					for m in f:
						if m.abspath==fileInfo.abspath:
							pass # a file is not a duplicate of itsself
						elif m==fileInfo:
							return m
		return None
		
	def addFile(self,fileInfo):
		if type(fileInfo)==str or type(fileInfo)==unicode:
			fileInfo=FileInfo(fileInfo)
		if not self._db.has_key(fileInfo.extension()):
			self._db[fileInfo.extension()]={fileInfo.short():[fileInfo]}
		else:
			ext=self._db[fileInfo.extension()]
			if not ext.has_key(fileInfo.short()):
				ext[fileInfo.short()]=[fileInfo]
			else:
				ext[fileInfo.short()].append(fileInfo)
		
	def _fDupCb(self,file,skipExt,ignoreDirs,context):
		if os.path.isfile(file):
			fi=FileInfo(file)
			if fi.size()>0 and not fi.extension() in skipExt:
				path=fi.abspath.split(os.sep)[0:-1]
				ignore=False
				for d in path:
					if d in ignoreDirs:
						ignore=True
						break
				if not ignore:
					dup=self._hasDup(fi)
					if dup==None:
						self.addFile(fi)
					else:
						if self.dupFoundFn!=None:
							self.dupFoundFn(fi.abspath,dup.abspath,self.dupFoundArgs,self.dupFoundKwArgs)
						self.dups.append((fi.abspath,dup.abspath))
		
	def findDuplicates(self,startDir,skipExt=['lnk'],ignoreDirs=['.bzr','.git','bin','lib'],dupFoundFn=None,*args,**kwargs):
		"""
		startDir can be a list od dirs
		
		Returns [(filename,duplicateFilename)]
		"""
		import threadedFileWalker,progressDialog
		self.dups=[]
		# find all the files
		dialog=progressDialog.ProgressDialog(title='Finding Duplicate Files',text1="Scanning directory structure...",maxRange=100,iconFile=None,cylonStyle=True,autoClose=True)
		fw=threadedFileWalker.ThreadedFileWalker(startDir,True,dialog,8)
		fw.run()
		allFiles=fw.getFiles()
		binnedFiles=fw.getFilesByType()
		# now visit all of them
		self.dupFoundFn=dupFoundFn
		self.dupFoundArgs=args
		self.dupFoundKwArgs=kwargs
		dialog=progressDialog.ProgressDialog(title='Finding Duplicate Files',text1="[%d Files] Finding duplicates..."%len(allFiles),maxRange=len(allFiles),iconFile=None,cylonStyle=False,autoClose=False)
		fw=threadedFileWalker.ThreadedFileWalker(allFiles,False,dialog,8)
		fw.run(self._fDupCb,skipExt,ignoreDirs,fw)
		return self.dups
		
	def listDupsOld(self,startDir,skipExt=['lnk'],ignoreDirs=['.bzr','.git','bin','lib'],context=None):
		"""
		startDir can be a list od dirs
		
		Returns [(filename,duplicateFilename)]
		"""
		dups=[]
		if type(startDir)==list:
			for d in startDir:
				dups.extend(self.listDups(d))
			return dups
		for here,dirnames,filenames in os.walk(startDir):
			for f in filenames:
				fi=FileInfo(here+os.sep+f)
				if fi.size()<=0:
					continue
				if fi.extension() in skipExt:
					continue
				path=fi.abspath.split(os.sep)[0:-1]
				ign=False
				for d in path:
					if d in ignoreDirs:
						ign=True
						break
				if ign:
					continue
				dup=self._hasDup(fi)
				if dup==None:
					self.addFile(fi)
				else:
					dups.append((fi.abspath,dup.abspath))
			#for d in dirnames:
			#	TODO: check if all files are dup from another dir, then this dir is simply a dup of that!
		return dups
		
if __name__ == '__main__':
	import sys
	# Use the Psyco python accelerator if available
	# See:
	# 	http://psyco.sourceforge.net
	try:
		import psyco
		psyco.full() # accelerate this program
	except ImportError:
		pass
	d=DupliGator()
	if len(sys.argv)>1:
		f=open('duplicateFiles.csv','w')
		def dupFoundFn(f1,f2):
			f.write(f1+','+f2)
			f.flush()
		d.findDuplicates(sys.argv[1:])
		f.close()
	else:
		print 'USEAGE: dupligator.py dir [dir...]'
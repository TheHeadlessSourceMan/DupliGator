# TODO: currently the multiprocessing stuff does not work
# due to the fact it wants to serialize the dialog!
import progressDialog
import os


def PROCESS_CLASSES(prefer=None):
	"""
	Find appropriate Process classes for whatever multi-processing library you
	are using (supports threading as well as pathos, pyina, and the standard multiprocessing)
	
	prefer can be "threading","multiprocessing","pathos", or "pyina"
	if the preference is not installed for some reason, it will get the next best one
	
	Returns (ProcessClass,QueueClass)
	"""
	if prefer=='threading':
		import threading
		import Queue
		return (threading.Thread,Queue.Queue)
	if prefer=='pathos' or prefer==None:
		try:
			import pathos.multiprocessing
			return (pathos.multiprocessing.Process,pathos.multiprocessing.JoinableQueue)
		except ImportError:
			prefer=None
	if prefer=='pyina' or prefer==None:
		try:
			import pyina.multiprocessing
			return (pyina.multiprocessing.Process,pyina.multiprocessing.JoinableQueue)
		except ImportError:
			prefer=None
	import multiprocessing
	return (multiprocessing.Process,multiprocessing.JoinableQueue)
		
		
class ThreadedWorker:
	def __init__(self,initialWork=None,progressWatcher=None,numThreads=8,preferredProcess=None):
		"""
		initialWork can be a single work item or a list of individual work items
		
		progressWatcher - object can implement any of this stuff:
				__iadd__(amount) to increment
				write(text) to write message
				run(function) so a ui can pump runloop messages for this class
			it should work fine with progressDialog object or any file-like object
		
		"""
		self.numThreads=numThreads
		self.progressWatcher=progressWatcher
		self._threads=[]
		self._printThreadThread=None;
		self._progressWatcherThreadThread=None;
		self.processClasses=PROCESS_CLASSES(preferredProcess)
		self.workQ=self.processClasses[1]()
		self.printQ=self.processClasses[1]()
		self.progressWatcherMessageQ=self.processClasses[1]() # mix of both numerics to increment the bar and text to display
		self.addWork(initialWork)
		self._running=False
		
	def __getstate__(self):
		"""
		special function that returns an dict of all serialize members
		"""
		noPickleValues=[
				'_threads',
				'_printThreadThread',
				'_progressWatcherThreadThread',
				'progressWatcher',
				'processClasses'
			]
		items=dict(self.__dict__)
		for name in noPickleValues:
			items[name]=None
		return items
		
	def addWork(self,work):
		if work!=None:
			if type(work)==list:
				for w in work:
					self.workQ.put(w)
			else:
				self.workQ.put(work)
		
	def _printThread(self):
		while self._running:
			try:
				text=self.printQ.get(block=False,timeout=100)
			except Exception: # timeout
				continue
			print text
		print 'Print thread exited'
	
	def _progressWatcherThread(self):
		while self._running:
			try:
				v=self.progressWatcherMessageQ.get(block=False,timeout=100)
			except Exception: # timeout
				continue
			if type(v) in [str,unicode]:
				if self.progressWatcher!=None and hasattr(self.progressWatcher,'write'):
					self.progressWatcher.write(v)
			else:
				if self.progressWatcher!=None and hasattr(self.progressWatcher,'__iadd__'):
					self.progressWatcher+=v
		print 'Progress thread exited'
		
	def _workerThread(self):
		while self._running:
			try:
				w=self.workQ.get(block=False,timeout=100)
			except Exception: # timeout
				continue
			if self.cbFunction!=None:
				try:
					self.cbFunction(w,*self.cbFunctionArgs,**self.cbFunctionKwArgs)
				except Exception:
					import traceback,sys
					exc_type,exc_value,exc_traceback=sys.exc_info()
					self._print('\n'.join(traceback.format_exception(exc_type,exc_value,exc_traceback)))
			if self.progressWatcher!=None:
				self.progressWatcher+=1
			self.workQ.task_done()
		print 'worker thread exited'
			
	def _print(self,*args):
		"""
		a substitute for the python print statement
		to dump program output to the console
		"""
		args=[str(a) for a in args]
		self.printQ.put(' '.join(args))
		
	def addProgressMessage(self,*args):
		"""
		add a message to the user feedback
		"""
		args=[str(a) for a in args]
		self.progressWatcherQ.put(' '.join(args))
		
	def addProgress(self,amount=1):
		"""
		increment the progress to the user feedback
		"""
		self.progressWatcherQ.put(amount)
		
	def run(self,cbFunction=None,*args,**kwargs):
		"""
		Runs the function across multiple threads until all the work is completed.
		
		cbFunction - call this function for every work item in the list
			first argument is ALWAYS the work item, then *args and **kwargs
		"""
		import threading
		self._printThreadThread=threading.Thread(target=self._printThread);
		self._progressWatcherThreadThread=threading.Thread(target=self._progressWatcherThread);
		if cbFunction:
			if len(self.visited)>0:
				self.reset()
			self.cbFunction=cbFunction
			self.cbFunctionArgs=args
			self.cbFunctionKwArgs=kwargs
			self._threads=[]
			self._running=True
			for i in range(self.numThreads):
				p=self.processClasses[0](target=self._workerThread)
				self._threads.append(p)
				p.start()
			if self.progressWatcher!=None and hasattr(self.progressWatcher,'run'):
				self.progressWatcher.run(self.workQ.join)
			else:
				self.workQ.join()
			self._running=False
			for t in self._threads:
				t.join()
			self._threads=[]
			

class ThreadedFileWalker(ThreadedWorker):
	def __init__(self,startDir,visitSubDirs=True,progressWatcher=None,numThreads=8,preferredProcess=None):
		"""
		startDir can be a single dir or a list
		"""
		ThreadedWorker.__init__(self,startDir,progressWatcher,numThreads,preferredProcess)
		self.visitSubDirs=visitSubDirs
		self.visited={}
			
	def getFilesByType(self,synonymousExtensions=[['jpeg','jpg','jpe'],['html','htm']]):
		"""
		synonymousExtensions - used to combine all extensions that mean the same thing together
			for instance synonymousExtensions=[['html','htm']] would put 'foo.htm' in the 'html' bin 
		
		returns {extension:files}
		NOTE: the [''] entry contains all files without an extension!
		NOTE: the [None] entry contains all directories
		"""
		ret={}
		for f in self.getFiles():
			if os.path.isdir(f):
				ext=None
			else:
				ext=f.rsplit(os.sep,1)[-1].rsplit('.',1)
				if len(ext)>1:
					ext=ext[-1].lower()
					for s in synonymousExtensions:
						if ext in s:
							ext=s[0]
							break
				else:
					ext='' # no extension
			if not ret.has_key(ext):
				ret[ext]=[f]
			else:
				ret[ext].append(f)
		return ret
			
	def getFiles(self):
		if len(self.visited)==0:
			self.run()
		return self.visited.keys()
			
	def getCount(self):
		return len(self.getFiles())
			
	def reset(self):
		"""
		reset this walker to walk yet again
		(This is slightly more efficient than creating a new one)
		
		No need to call this manually.  It will be automatically reset next time you call run().
		"""
		for d in self.visited.keys():
			self.addWork(d)
		self.visited={}
			
	def addDir(self,dir):
		if type(dir)==list:
			self.addWork([os.path.abspath(d) for d in dir])
		else:
			self.addWork(os.path.abspath(dir))
		
	def run(self,cbFunction=None,*args,**kwargs):
		self.fileCbFunction=cbFunction
		ThreadedWorker.run(self,self._fileIntermediateCb,*args,**kwargs)
		
	def _fileIntermediateCb(self,f,*args,**kwargs):
		"""
		This is called in before the cbFunction() and is what we use to walk the directory
		"""
		if not self.visited.has_key(f):
			self.visited[f]=None # add it to the visited list
			if self.progressWatcher!=None:
				self.progressWatcher.setMessage(f)
			if self.fileCbFunction!=None:
				self.fileCbFunction(f,*self.cbFunctionArgs,**self.cbFunctionKwArgs)
			if self.visitSubDirs and os.path.isdir(f):
				self.addWork([f+os.sep+ff for ff in os.listdir(f)]) # add the contents of the directory


def _inc(dir,count):
	count.count+=1
class _Count:
	def __init__(self):
		self.count=0
def countFiles(dir,dialog=True):
	"""
	Sure the class provides this functionality, but 
	this is mainly here as an example.
	"""
	if dialog:
		dialog=progressDialog.ProgressDialog(title='Finding all Files',text1='Scanning...',maxRange=100,iconFile=None,cylonStyle=True,autoClose=True)
	else:
		dialog=None
	count=_Count()
	fw=ThreadedFileWalker(dir,True,dialog,2,preferredProcess='multiprocessing')
	fw.run(_inc,count)
	return count.count
	
	
def _printFile(f):
	print f
def printFiles(dir,processes=8,dialog=False):
	"""
	prints all the visited files
	
	NOTE: could be out of order due to threading
	"""
	import time
	start=time.time()
	if dialog:
		dialog=progressDialog.ProgressDialog(title='Finding all Files',text1='Scanning...',maxRange=100,iconFile=None,cylonStyle=True,autoClose=True)
	else:
		dialog=None
	fw=ThreadedFileWalker(dir,dialog,processes,preferredProcess=None)
	fw.run(_printFile)
	end=time.time()
	print 'TIME:',end-start,'sec'
	return end-start
	
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
	if False: # test file type binning
		fw=ThreadedFileWalker(sys.argv[1:],None,2)
		files=fw.getFilesByType()
		print files['jpeg']
	if True: # test the progress dialog
		print countFiles(sys.argv[1:],True)
	if False: # determine how many files can be processed per number of threads
		count=countFiles(sys.argv[1:])
		results=[]
		for i in range(1,10):
			t=printFiles(sys.argv[1:],i)
			results.append((i,t))
		print ''
		print count,'FILES'
		print 'PROC\tTIME\tFILES/SEC'
		for r in results:
			print str(r[0])+'\t'+str(r[1])+'\t'+str(count/r[1])
	print 'SUCCESS!'
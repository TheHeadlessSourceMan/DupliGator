from Tkinter import *
import ttk
import threading,Queue


def EnableTitlebarIcon(hWnd,icon=0,enable=True):
	"""
	Greys out titlebar icons
	
	icon - is:
		0 - close icon
		1 - maximize icon
		2 - minimize icon
	
	NOTE: Only works with windows
	NOTE: Only works while mainloop() is running 
		therefore immediately before mainloop() you may want to:
			root.after(50,EnableTitlebarIcon,root.winfo_id(),enable)
	"""
	import win32gui
	SC_MINIMIZE=0xF020
	SC_MAXIMIZE=0xF030
	SC_CLOSE=0xF060
	MF_ENABLED=0x00000000
	MF_GRAYED=0x00000001
	MF_DISABLED=0x00000002
	control=[SC_CLOSE,SC_MAXIMIZE,SC_MINIMIZE][icon]
	while True:
		hMenu=win32gui.GetSystemMenu(hWnd,0)
		if hMenu!=0:
			break
		parent=win32gui.GetParent(hWnd)
		if parent==0:
			msg=['ERR: Top-level parent has no system menu.',
				'',
				'NOTE: Only works while mainloop() is running',
				'	therefore immediately before mainloop() you may want to:',
				'		root.after(50,EnableTitlebarCloseIcon,root.winfo_id(),enable)'
				]
			raise Exception('\n'.join(msg))
		hWnd=parent
	if enable:
		#print 'enabling',hWnd,hMenu
		win32gui.EnableMenuItem(hMenu,control,MF_ENABLED)
	else:
		#print 'disabling',hWnd,hMenu
		win32gui.EnableMenuItem(hMenu,control,MF_GRAYED)


class ProgressDialog(Frame):
	def __init__(self,title='Progress...',text1=None,maxRange=100,iconFile=None,cylonStyle=False,autoClose=False):
		"""
		title - the dialog title
		text1 - an optional text to display above the progress text area 
			can be None to leave it off
		maxRange - use to set how many items are expected for instance, if you are copying 207 files
			then you can go dialog+=1 for each file
		iconFile - specify an icon for the dialog
		cylonStyle - causes the progress bar to bounce back and forth 
			as opposed to a regular progress bar with a beginning and an end
		autoClose - automatically close the window when complete 
			the alternative is an OK button that the user must click to close the window
		"""
		self.title=title
		self.text1=text1
		self.maxRange=maxRange
		self.cylonStyle=cylonStyle
		self.autoClose=autoClose
		self.pos=0
		self.okToExit=False
		# initialize ui
		self.parent=None
		if self.parent==None:
			self.parent=Tk()
			self.parent.wm_title(title)
			self.parent.minsize(250,100)
			#self.parent.resizable(0,0)
			#self.parent.attributes("-toolwindow",1)
			if iconFile!=None:
				self.parent.iconbitmap(default=iconFile)
				self.parent.protocol('WM_DELETE_WINDOW',self.onWindowX)
		Frame.__init__(self,self.parent)
		self.pack(fill=BOTH,expand=1)
		self._createWidgets()
		self._messageQ=Queue.Queue(1)
		self._closeDisabled=False
		
	def _createWidgets(self):
		self._commandsThread=None
		self.grid_columnconfigure(0,weight=1)
		# add controls
		row=0
		if self.text1!=None:
			label=Label(self,text=self.text1)
			label.grid(row=row,column=0,columnspan=2,sticky='WN')
			row=row+1
		self._tkMessage=Text(self,state='normal',height=4,bg='gray')
		self._tkMessage.grid(row=row,column=0,sticky='EWNS')
		scroll=Scrollbar(self,command=self._tkMessage.yview)
		scroll.grid(row=row,column=1,sticky='ENS')
		self._tkMessage.config(yscrollcommand=scroll.set)
		row=row+1
		if self.cylonStyle:
			self._tkProgressbar=ttk.Progressbar(self,orient=HORIZONTAL,mode='indeterminate')
		else:
			self._tkProgressbar=ttk.Progressbar(self,orient=HORIZONTAL,mode='determinate')
		self._tkProgressbar.grid(row=row,column=0,columnspan=2,sticky='EWS')
		row=row+1
		if not self.autoClose:
			self._tkButton=Button(self,text= 'OK',command=self.onOk,state='disabled')
			self._tkButton.grid(row=row,column=0,columnspan=2,sticky='S')
			row=row+1
		
	def onOk(self):
		self.parent.destroy()
		
	def __add__(self,amount):
		if type(amount) not in [int,float]:
			amount=float(amount)
		self.inc(amount)
		return self
	def __iadd__(self,amount):
		self.inc(amount)
		return self    
	def inc(self,amount=1):
		self.pos+=amount
		
	def write(self,newText=None):
		if self._messageQ.full():
			self._messageQ.get() # remove one to make room
		self._messageQ.put(newText)
		
	def _setMessage(self,newText=None):
		self._tkMessage.delete('1.0',END)
		if newText!=None:
			self._tkMessage.insert(END,newText)
	
	def _updateThread(self):
		if self._commandsThread==None or self._commandsThread.isAlive(): # check again in 1/4 second
			if self.cylonStyle:
				self._tkProgressbar.step(1)
				self._lastPercent=self.pos
			else:
				percent=min((self.pos/float(self.maxRange))*100,100)
				if percent>self._lastPercent+0.01: # only redraw if a significant step was made
					self._tkProgressbar["value"]=percent
					self._lastPercent=percent
			if not self._messageQ.empty():
				self._setMessage(self._messageQ.get())
			self.parent.after(250,self._updateThread)
			if not self._closeDisabled:
				self._closeDisabled=True
				EnableTitlebarIcon(self.parent.winfo_id(),0,False)
				EnableTitlebarIcon(self.parent.winfo_id(),1,False)
		else:
			self._okToExit()
			
	def _okToExit(self,message=None):
		if message!=None:
			self._setMessage(message)
		elif not self._messageQ.empty():
			self._setMessage(self._messageQ.get())
		if not self.cylonStyle:
			self._tkProgressbar["value"]=100
		self.okToExit=True
		if self.autoClose:
			self.parent.destroy()
		else:
			self._tkButton.config(state='active')	
			if self._closeDisabled:
				self._closeDisabled=False
				EnableTitlebarIcon(self.parent.winfo_id(),0,True)
		
	def onWindowX(event=None):
		"""
		when the X button is pressed in the corner of the window
		
		NOTE: this doesn't seem to work on Windows.  Maybe other OSes are more lucky.
		"""
		if self.okToExit:
			self.parent.destroy()
	
	def run(self,commandsFunction=None,*args,**kwargs):
		"""
		run this dialog
		
		commandsFunction - a long-running function that you want to run
			this function MUST increment this dialog as it proceeds (e.g. dialog+=1)
			it should also call write() periodically
			when this function exits, this dialog will become dismissable
			TIP: you may want to put the entire contents of the function in a try: clause
				and write() any errors
		args and kwargs are passed directly through to commandsFunction
		
		TIP: the __main__ section of this file provides an example if you're still confused
		"""
		self._lastPercent=0;
		if commandsFunction!=None:
			self._commandsThread=threading.Thread(target=commandsFunction,args=args,kwargs=kwargs)
		self._tkProgressbar["value"]=0
		if self._commandsThread!=None:
			self._commandsThread.start()
		self.parent.after(250,self._updateThread)
		self.parent.mainloop()
		if self._commandsThread!=None:
			self._commandsThread.join()
		
		
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
	import time
	d=ProgressDialog(cylonStyle=True)
	def commandsFunction(d):
		try:
			for x in range(200):
				d+=1
				d.write('Item '+str(x))
				time.sleep(0.01)
			# print undefinedVariable # uncomment to test exceptions
			d.write('DONE!')
		except Exception:
			exc_type,exc_value,exc_traceback=sys.exc_info()
			import traceback
			d.write('\n'.join(traceback.format_exception(exc_type,exc_value,exc_traceback)))
	d.run(commandsFunction,d)
	
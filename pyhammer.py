import sys
import os.path
import getopt
import numpy as np
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from time import time
from spectrum import Spectrum
from eyecheck import Eyecheck

def main(options):
    """
    The main method of PyHammer which executes the overarching procedure.

    Description:
        This is the main part of the code that executes the
        actual pyhammer algorithms. This is arrived at either
        by startCmd or StartGUI, both of which get all the
        necessary options from the user and pass them to
        this function. The general process of this function
        should be to:
        
        - Define a Spectrum object to be used in reading files.
        - Load each spectrum sequentially.
        - Guess the spectral type.
        - Use the best guess for the spectral type and find the radial
          velocity shift. Shift the spectrum to rest.
        - Guess the spectral type again.
        - Repeat for all spectra
        - Bring up eyecheck GUI.

    Input:
        options: A dict containing the options the user has specified.

    Output:
        This program outputs two files, an outfile and a rejectfile.
        The outfile contains all results of the spectral type guess
        as well as the user's eyecheck guess and the rejectfile contains
        the list of spectra which could not be classified for some reason.
    """

    # Create a Spectrum object
    spec = Spectrum()

    # If the user has decided to not skip to the eyecheck, let's
    # do some processing
    if not options['eyecheck']:
    
        # Open the input file
        try:
            infile = open(options['infile'], 'r')
        except IOError as e:
            notifyUser(options['useGUI'], str(e))
            return

        # Open and setup the output files
        outfile = open(options['outfile'], 'w')
        rejectfile = open(options['rejectfile'], 'w')
        outfile.write('#Filename,Radial Velocity (km/s),Guessed Spectral Type,Guessed Metallicity,User Spectral Type,User Metallicity\n')
        rejectfile.write('#Filename,File Type,Spectra S/N\n')

        # Define the string to contain all failure messages. These will be compiled
        # and printed once at the end, if anything is put into it.
        rejectMessage = ''

        for i, line in enumerate(infile):
            # Remove extra whitespace and other unwanted characters and split
            line = line.strip()
            if line.find(',') > 0: line = line.replace(',',' ')
            fname, ftype = ' '.join(line.split()).rsplit(' ',1)

            # Print statement of progress for user
            print(i+1, ') Processing ', os.path.basename(fname), sep = '')

            # Now read in the current file (this process reads in the file, converts air to 
            # vac when necessary and interpolates onto the template grid)
            success, message = spec.readFile(options['spectraPath']+fname, ftype)

            # If the attempt at reading the file did not succeed, then we
            # should just continue
            if not success:
                rejectfile.write(fname + ',' + ftype + ',N/A\n')
                rejectMessage += 'FILE: ' + fname + '  REASON: ' + message.replace('\n','') + '\n'
                continue

            # Now that we have the necessary data in the spec object, let's
            # begin processing.

            # --- 1 ---
            # Calculate the signal to noise of the spectrum to potentially reject
            if options['sncut'] is not None:
                snVal = spec.calcSN()
                if snVal < options['sncut']:
                    rejectfile.write(fname + ',' + ftype + ',' + str(snVal) + '\n')
                    rejectMessage += 'FILE: ' + fname + '  REASON: S/N = ' + str(snVal) + ' < ' + str(options['sncut']) + '\n'
                    continue
            
            # --- 2 ---
            # Normalize the input spectrum to the same place where the templates are normalized (8000A)
            spec.normalizeFlux()

            # --- 3 ---
            # Call guessSpecType function for the initial guess
            # this function measures the lines then makes a guess of all parameters
            spec.guessSpecType()

            # --- 4 ---
            # Call findRadialVelocity function using the initial guess
            shift = spec.findRadialVelocity()

            # --- 5 ---
            # Call shiftToRest that shifts the spectrum to rest wavelengths
            spec.shiftToRest(shift)

            # --- 6 ---
            # Repeat guessSpecType function to get a better guess of the spectral 
            # type and metallicity 
            spec.guessSpecType()

            # End of the automatic guessing. We should have:
            #  1. Spectrum object with observed wavelength, flux, var,
            #  2. rest wavelength,
            #  3. spectral type (guessed),
            #  4. radial velocity and uncertainty,
            #  5. metallicity estimate,
            #  6. and line indice measurements

            # --- 7 ---
            
            # Translate the numbered spectral types into letters
            letterSpt = ['O', 'B', 'A', 'F', 'G', 'K', 'M', 'L'][spec.guess['specType']]
            
            # Write the file
            outfile.write(fname + ',' + str(shift) + ',' + letterSpt + str(spec.guess['subType']) +
                          ',' + '{:+2.1f}'.format(spec.guess['metal']) + ',nan,nan' + '\n')
        
        # We're done so let's close all the files.
        infile.close()
        outfile.close()
        rejectfile.close()

        # Check that we processed every spectrum in the infile. If not, print out
        # the reject method.
        if rejectMessage != '':
            # Prepend to the reject message
            rejectMessage = 'The following is a list of rejected spectra\n' \
                            'along with the reason for its rejection.\n\n' + rejectMessage
            notifyUser(options['useGUI'], rejectMessage)
            # Check if all spectra were skipped by seeing if the number of
            # lines in the reject message is equal to the number of spectra
            # processed (plus three lines for the prepended message). If
            # they were all skipped, theres nothing to eyecheck so return.
            if rejectMessage.count('\n') == i+4:
                notifyUser(options['useGUI'], 'All spectra were bad. Exiting PyHammer.')
                # Clean up any temporary input files created
                if os.path.basename(options['infile'])[:11] == 'temp_input_':
                    os.remove(options['infile'])
                return
    
    # At this point, we should call up the GUI to do the eyechecking.
    Eyecheck(spec, options)

    # Clean up any temporary input files created
    if os.path.basename(options['infile'])[:11] == 'temp_input_':
        os.remove(options['infile'])

def notifyUser(useGUI, message):
    """
    Description:
        A method for handling sending messages to the
        user during the execution of the main function.
        The reason for making this a separate function
        is to handle where we need to send the message.
        If the user started using a GUI, we want to
        use a GUI to notify them, otherwise, if they
        were using the command line, print to the command
        line.

    Input:
        useGUI: A boolean indicating whether or not to
            use a GUI to notify the user. This is set
            in the options dict.
        message: The message to present to the user.
    """

    if not useGUI:
        # Simple case, just print the message.
        print(message, flush = True)
    else:
        # More involved case, create a tk window to
        # display the message.
        root = tk.Tk()
        root.title('PyHammer Notification')
        root.iconbitmap(os.path.join(os.path.split(__file__)[0],'resources','sun.ico'))
        root.resizable(False,False)
        root.geometry('+100+100')
        
        label = ttk.Label(root, text = message, font = '-size 10')
        label.grid(row = 0, column = 0, padx = 2, pady = 2)
        but = ttk.Button(root, text = 'OK', command = root.destroy)
        but.grid(row = 1, column = 0, sticky = 'nsew', padx = 2, pady = 5)
        root.rowconfigure(1, minsize = 40)
        root.columnconfigure(0, minsize = 200)

        root.mainloop()

def showHelpWindow(root, helpText):
    """
    Description:
        This brings up a new window derived from root
        that displays helpText and has a button to close
        the window when user is done.

    Input:
        root: A tkinter Tk() window to derive the new
            help window from
        helpText: This should be a string to display
    """
    
    helpWindow = tk.Toplevel(root)
    helpWindow.grab_set()
    helpWindow.title('PyHammer Help')
    helpWindow.iconbitmap(os.path.join(os.path.split(__file__)[0],'resources','sun.ico'))
    helpWindow.resizable(False, False)
    helpWindow.geometry('+%i+%i' % (root.winfo_rootx()+50, root.winfo_rooty()+50))
    
    label = ttk.Label(helpWindow, text = helpText, font = '-size 10')
    label.grid(row = 0, column = 0, padx = 2, pady = 2)
    but = ttk.Button(helpWindow, text = 'OK', command = helpWindow.destroy)
    but.grid(row = 1, column = 0, sticky = 'nsew', padx = 2, pady = 5)
    helpWindow.rowconfigure(1, minsize = 40)

class StartGUI(object):

    def __init__(self, options):

        self.options = options

        # --- Main GUI Settings ---
    
        self.root = tk.Tk()
        self.root.title('PyHammer Settings')
        self.root.iconbitmap(os.path.join(os.path.split(__file__)[0],'resources','sun.ico'))
        self.root.resizable(False,False)
        self.root.geometry('+100+100')
        self.style = ttk.Style()
        self.defaultColor = self.style.lookup('TButton', 'foreground')
        self.style.configure('create.TButton', foreground = self.defaultColor)
        self.root.configure(background = self.style.lookup('TButton', 'background'))

        # --- Main GUI Widgets ---
        
        self.label = ttk.Label(self.root, text = 'Provide an input file')
        self.label.grid(row = 0, column = 0, columnspan = 2, padx = 2, pady = (2,1))
        self.frame = ttk.Frame(self.root, relief = tk.FLAT)
        self.frame.grid(row = 1, column = 0, columnspan = 2, padx = 2, pady = (1,3), sticky = 'nsew')
        self.prevButton = ttk.Button(self.root, text = 'Previous', command = self.prevOption)
        self.prevButton.grid(row = 2, column = 0, padx = (2,1), pady = 1, sticky = 'nsew')
        self.nextButton = ttk.Button(self.root, text = 'Next', command = self.nextOption)
        self.nextButton.grid(row = 2, column = 1, padx = (1,2), pady = 1, sticky = 'nsew')
        self.startButton = ttk.Button(self.root, text = 'Start  PyHammer', command = self.goToMain)
        self.startButton.grid(row = 3, column = 0, columnspan = 2, padx = 2, pady = (1,2), sticky = 'nsew')

        self.root.columnconfigure(0, minsize = 10, weight = 1)
        self.root.columnconfigure(1, minsize = 10, weight = 1)

        # --- Frame Widgets ---

        # Help Button
        self.helpButton = ttk.Button(self.frame, text = '?', width = 2)
        # Browse Button
        self.browseButton = ttk.Button(self.frame, text = 'Browse')
        # Create Button
        self.createPressed = False
        self.createButton = ttk.Button(self.frame, text = 'Create', command = self.createInputFile, style = 'create.TButton')
        # Create Frame
        self.createFrame = ttk.Frame(self.frame, relief = tk.FLAT)
        # Input Filename
        self.infile = tk.StringVar(value = ('' if options['infile'] is None else options['infile']))
        self.infileEntry = ttk.Entry(self.frame, textvariable = self.infile)
        # Output Filename
        self.outfile = tk.StringVar(value = options['outfile'])
        self.outfileEntry = ttk.Entry(self.frame, textvariable = self.outfile)
        # Reject Filename
        self.rejectfile = tk.StringVar(value = options['rejectfile'])
        self.rejectfileEntry = ttk.Entry(self.frame, textvariable = self.rejectfile)
        # Spectra Full Path Buttons
        self.fullPath = tk.IntVar(value = (0 if options['fullPath'] is None else options['fullPath']))
        self.fullPathYes = ttk.Radiobutton(self.frame, text = 'Yes', value = 1, variable = self.fullPath)
        self.fullPathNo = ttk.Radiobutton(self.frame, text = 'No', value = 0, variable = self.fullPath)
        # Spectra File Path
        self.spectraPath = tk.StringVar(value = ('' if options['spectraPath'] is None else options['spectraPath']))
        self.spectraPathEntry = ttk.Entry(self.frame, textvariable = self.spectraPath)
        # Skip to Eyecheck
        self.eyecheck = tk.IntVar(value = (0 if options['eyecheck'] is None else options['eyecheck']))
        self.eyecheckYes = ttk.Radiobutton(self.frame, text = 'Yes', value = 1, variable = self.eyecheck, command = lambda: self.nextButton.configure(state = 'disabled'))
        self.eyecheckNo = ttk.Radiobutton(self.frame, text = 'No', value = 0, variable = self.eyecheck, command = lambda: self.nextButton.configure(state = 'normal'))
        # S/N Cutoff
        self.sncut = tk.StringVar(value = ('' if options['sncut'] is None else options['sncut']))
        self.sncutEntry = ttk.Entry(self.frame, textvariable = self.sncut)

        # --- Create Frame Widgets ---

        # Define widgets
        self.createWindow = tk.Text(self.createFrame, relief = tk.FLAT, wrap = tk.NONE, font = '-family courier -size 10')
        scrollV = ttk.Scrollbar(self.createFrame, command = self.createWindow.yview)
        scrollH = ttk.Scrollbar(self.createFrame, orient = tk.HORIZONTAL, command = self.createWindow.xview)
        genFromDirectory = ttk.Button(self.createFrame, text = 'Generate From Directory', command = self.createInputFromDirectory)
        ttk.Separator(self.createFrame, orient = tk.VERTICAL).grid(row = 2, column = 1, padx = 4, stick = 'wns')
        applyType = ttk.Button(self.createFrame, text = 'Apply Data Type', command = self.applyType)
        self.dataType = tk.StringVar()
        dataTypeEntry = ttk.Entry(self.createFrame, textvariable = self.dataType, width = 10)

        # Layout Widgets
        self.createWindow.grid(row = 0, column = 0, columnspan = 4)
        scrollV.grid(row = 0, column = 4, sticky = 'ns')
        scrollH.grid(row = 1, column = 0, columnspan = 4, sticky = 'ew')
        genFromDirectory.grid(row = 2, column = 0, sticky = 'w')
        applyType.grid(row = 2, column = 2, padx = (0,4), sticky = 'w')
        dataTypeEntry.grid(row = 2, column = 3, sticky = 'w')
        self.createFrame.columnconfigure(3, weight = 1)
        self.createWindow.configure(yscrollcommand = scrollV.set, xscrollcommand = scrollH.set)

        # --- Help Text ---

        self.infileHelpText = (
            'You should include the full path to the input file\n'
            'which contains a list of spectra files to process.\n'
            'However, if the input file is located in the pyhammer.\n'
            'folder, then simply the filename will suffice.')
        self.outfileHelpText = (
            'You should include the full path to the output file\n'
            'which will contain the results of PyHammer. However,\n'
            'if no path is supplied, the file will be saved to the\n'
            'the pyhammer folder. The output file is, by default,\n'
            'set to PyHammerResults.csv unless specified otherwise.\n'
            'The output filetype should be a .csv file.')
        self.rejectfileHelpText = (
            'You should include the full path to the reject file\n'
            'which will contain the list of any spectra unable to\n'
            'be classified. However, if no path is supplied, the\n'
            'file will be saved to the the pyhammer folder. The\n'
            'reject file is, by default, set to RejectSpectra.csv\n'
            'unless specified otherwise. The reject filetype should\n'
            'be a .csv file.')
        self.fullPathHelpText = (
            'Choose whether or not the spectra listed in your input\n'
            'file have a full path specified. If you choose no, you\n'
            'will need to specify the full path to the spectra.')
        self.spectraPathHelpText = (
            'If your spectra list does not contain the full path\n'
            'to the files in the name, provide a path to prepend\n'
            'to each spectra filename.')
        self.eyecheckHelpText = (
            'If you have already classified your spectra you can\n'
            'choose to skip directly to checking them by eye, rather\n'
            'than re-running the classification algorithm again. Note\n'
            'that you cannot skip to eye checking without first\n'
            'classifying your spectra and creating an output file.')
        self.sncutHelpText = (
            'If you would like to only classify spectra with a S/N\n'
            'above a threshold, provide that value here. If you do not\n'
            'want to provide a cutoff, leave this field blank. This\n'
            'option does not apply if you choose to skip to the eyecheck.')

        # --- Setup and Start ---

        self.root.bind('<Tab>', lambda event: self.nextOption())
        self.root.bind('<Shift-Tab>', lambda event: self.prevOption())

        self.firstSetting = 0 # The index number of the first setting the user can input
        self.curSetting = 0   # Keep track of which input option the user is on
        self.lastSetting = 6  # The index number of the last setting the user can input
        self.updateGUI()
        
        self.root.mainloop()

    def prevOption(self):
        self.curSetting -= 1
        if self.curSetting == 4 and self.fullPath.get() == 1:
            self.curSetting -= 1
        self.updateGUI()

    def nextOption(self):
        self.curSetting += 1
        if self.curSetting == 4 and self.fullPath.get() == 1:
            self.curSetting += 1
        if self.curSetting >= 5 and self.eyecheck.get() == 1:
            self.lastSetting = 5
        else:
            self.lastSetting = 6
        self.updateGUI()

    def updateGUI(self):
        
        # Keep curSetting between between first and last setting
        self.curSetting = min(self.lastSetting, max(self.firstSetting, self.curSetting))
        
        # Change state of buttons as necessary
        self.prevButton.configure(state = ('disabled' if self.curSetting == self.firstSetting else 'normal'))
        self.nextButton.configure(state = ('disabled' if self.curSetting == self.lastSetting else 'normal'))

        # Remove all current widgets in frame
        for widget in self.frame.winfo_children():
            widget.grid_forget()

        # Define frame for current option input

        # --- Input File ---
        if self.curSetting == 0:
            self.label.configure(text = 'Provide an input file')
            self.infileEntry.grid(row = 0, column = 0, padx = 1, pady = 1, sticky = 'ew')
            self.browseButton.grid(row = 0, column = 1, padx = 1, pady = 1)
            self.browseButton.configure(command = lambda: self.browse(self.infileEntry, 'file'),
                                        state = ('disabled' if self.createPressed else 'normal'))
            self.createButton.grid(row = 0, column = 2, padx = 1, pady = 1)
            self.helpButton.grid(row = 0, column = 3, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.infileHelpText))

            self.frame.columnconfigure(0, minsize = 250, weight = 1)
            self.frame.columnconfigure(1, weight = 0)
            self.frame.columnconfigure(2, weight = 0)
            self.frame.columnconfigure(3, weight = 0)

            # Update create input file components if necessary
            if self.createPressed:
                self.createFrame.grid(row = 1, column = 0, columnspan = 4, padx = 2, pady = (2,5), sticky = 'nsew')

        # --- Output File ---
        elif self.curSetting == 1:
            self.label.configure(text = 'Provide an output file')
            self.outfileEntry.grid(row = 0, column = 0, padx = 1, pady = 1, sticky = 'ew')
            self.browseButton.grid(row = 0, column = 1, padx = 1, pady = 1)
            self.browseButton.configure(command = lambda: self.browse(self.outfileEntry, 'file'), state = 'normal')
            self.helpButton.grid(row = 0, column = 2, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.outfileHelpText))
            
            self.frame.columnconfigure(0, minsize = 250)

        # --- Reject File ---
        elif self.curSetting == 2:
            self.label.configure(text = 'Provide a reject file')
            self.rejectfileEntry.grid(row = 0, column = 0, padx = 1, pady = 1, sticky = 'ew')
            self.browseButton.grid(row = 0, column = 1, padx = 1, pady = 1)
            self.browseButton.configure(command = lambda: self.browse(self.rejectfileEntry, 'file'), state = 'normal')
            self.helpButton.grid(row = 0, column = 2, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.rejectfileHelpText))

            self.frame.columnconfigure(0, minsize = 250)

        # --- Full Path? ---
        elif self.curSetting == 3:
            self.label.configure(text = 'Do the spectra in the input file contain full paths?')
            self.fullPathYes.grid(row = 0, column = 0, padx = 5)
            self.fullPathNo.grid(row = 0, column = 1, padx = 5)
            self.helpButton.grid(row = 0, column = 2, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.fullPathHelpText))
            
            self.frame.columnconfigure(0, minsize = 0, weight = 1)
            self.frame.columnconfigure(1, weight = 1)
            self.frame.columnconfigure(2, weight = 0)

        # --- Spectra Path ---
        elif self.curSetting == 4:
            self.label.configure(text = 'Provide the path to the spectra files')
            self.spectraPathEntry.grid(row = 0, column = 0, padx = 1, pady = 1, sticky = 'ew')
            self.browseButton.grid(row = 0, column = 1, padx = 1, pady = 1)
            self.browseButton.configure(command = lambda: self.browse(self.spectraPathEntry, 'directory'), state = 'normal')
            self.helpButton.grid(row = 0, column = 2, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.spectraPathHelpText))

            self.frame.columnconfigure(0, minsize = 250)

        # --- Eyecheck? ---
        elif self.curSetting == 5:
            self.label.configure(text = 'Do you want to skip to classifying by eye?')
            self.eyecheckYes.grid(row = 0, column = 0, padx = 5)
            self.eyecheckNo.grid(row = 0, column = 1, padx = 5)
            self.helpButton.grid(row = 0, column = 2, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.eyecheckHelpText))
            
            self.frame.columnconfigure(0, minsize = 0, weight = 1)
            self.frame.columnconfigure(1, weight = 1)
            self.frame.columnconfigure(2, weight = 0)

        # --- S/N Cutoff ---
        elif self.curSetting == 6:
            self.label.configure(text = 'Enter a signal to noise cutoff')
            self.sncutEntry.grid(row = 0, column = 0, padx = 1, pady = 1, sticky = 'ew')
            self.helpButton.grid(row = 0, column = 1, padx = 1, pady = 1, sticky = 'e')
            self.helpButton.configure(command = lambda: showHelpWindow(self.root, self.sncutHelpText))
            
            self.frame.columnconfigure(0, minsize = 100, weight = 1)
            self.frame.columnconfigure(1, weight = 0)
            self.frame.columnconfigure(2, weight = 0)
            

    def createInputFile(self):
        self.createPressed = not self.createPressed # Invert boolean

        self.infileEntry.configure(state = ('disabled' if self.createPressed else 'normal'))
        self.style.configure('create.TButton', foreground = ('blue' if self.createPressed else self.defaultColor))
        
        self.updateGUI()

    def createInputFromDirectory(self):
        files = filedialog.askopenfilename(title = 'Select a directory', multiple = True, parent = self.root)
        for i, f in enumerate(files):
            self.createWindow.insert(tk.END, f+'\n'*(i+1 < len(files)))

    def applyType(self):
        datatype = self.dataType.get()
        if datatype == '':
            return
        lineCount = int(self.createWindow.index('end-1c').split('.')[0])
        for line in range(1, lineCount+1):
            curLine = self.createWindow.get('{}.0'.format(line), '{}.end'.format(line))
            comma = curLine.find(',')
            if comma >= 0:
                self.createWindow.delete('{}.{}'.format(line,comma),'{}.end'.format(line))
            self.createWindow.insert('{}.end'.format(line), ', '+datatype)

    def browse(self, entry, target = 'file'):
        if target == 'file':
            if entry is self.infileEntry:
                file = filedialog.askopenfilename(title = 'Select an input file', parent = self.root)
                if file != '':
                    self.infile.set(file)
            elif entry is self.outfileEntry:
                file = filedialog.asksaveasfilename(title = 'Select or create an output file', parent = self.root)
                if file != '':
                    self.outfile.set(file)
            elif entry is self.rejectfileEntry:
                file = filedialog.asksaveasfilename(title = 'Select a reject file', parent = self.root)
                if file != '':
                    self.rejectfile.set(file)
        if target == 'directory':
            if entry is self.spectraPathEntry:
                directory = filedialog.askdirectory(title = 'Select a directory', mustexist = True, parent = self.root)
                if directory != '':
                    self.spectraPath.set(directory)
    
    def goToMain(self):
        """
        Accepts as options all the input parameters from the
        gui so they can be used to update the options dict.
        First a check is done to make sure the user's input
        is valid. If it is, his will then progress to calling
        the main function with the options being passed to it.
        """
        # First make sure the user hasn't input anything bad
        
        message = ''    # The output message in case errors are found
        # Validate the input filename
        if not self.createPressed:
            if self.infile.get() == '':
                message += '- A spectra list filename was not provided.\n'
            else:
                if not os.path.isfile(self.infile.get()):
                    message += '- The input file cannot be found.\n'
        else:
            if self.createWindow.get('0.0',tk.END) == '\n':
                message += '- The text field for creating an input file is empty\n'
        # Validate the output filename
        if self.outfile.get() == '':
            message += '- An output filename was not provided.\n'
        else:
            outfileExt = self.outfile.get()[-4:]
            if outfileExt[0] == '.' and outfileExt[1:] != 'csv':
                message += '- The output file must be a csv file.\n'
        # Validate the reject filename
        if self.rejectfile.get() == '':
            message += '- A reject filename was not provided.\n'
        else:
            rejectExt  = self.rejectfile.get()[-4:]
            if rejectExt[0] == '.' and rejectExt[1:] != 'csv':
                message += '- The reject file must be a csv file.\n'
        if self.fullPath.get() == 0:
            if self.spectraPath.get() == '':
                message += '- A path for the spectra was not provided.\n'
            else:
                if not os.path.isdir(self.spectraPath.get()):
                    message += '- The spectra path is not a valid directory.\n'
        # Validate the skip to eyecheck
        if self.eyecheck.get() == 1 and not os.path.isfile(self.outfile.get()):
            message += '- You cannot skip to eyecheck without an existing output file.\n'
        # Validate the S/N cut
        if self.eyecheck.get() == 0 and self.sncut.get() != '':
            try:
                if float(self.sncut.get()) < 0:
                    message += '- The entered S/N cut must be greater than zero.\n'
            except ValueError as e:
                message += '- The entered S/N cut is not a valid number.\n'
        # Print out the message if there is one and return
        if message != '':
            message = 'The following issues were found with your input.\n' \
                      'Please correct them and try again.\n\n' + message
            notifyUser(True, message)
            return
            
        # If we've made it to this point, the user's inputs are valid. Store them
        # in the options dict and move to the main part of the code.
        if not self.createPressed:
            self.options['infile'] = self.infile.get()
        else:
            # Create a temporary input file based on what's in the createWindow text field
            fname = 'temp_input_'+str(int(time()))+'.txt'
            with open(fname, 'w') as f:
                f.write(self.createWindow.get('0.0', tk.END))
            self.options['infile'] = fname
        self.options['outfile'] = self.outfile.get() + '.csv'*(self.outfile.get()[-4:] != '.csv')
        self.options['rejectfile'] = self.rejectfile.get() + '.csv'*(self.rejectfile.get()[-4:] != '.csv')
        self.options['fullPath'] = (self.fullPath.get() == 1)
        self.options['spectraPath'] = self.spectraPath.get() * (not self.options['fullPath'])
        # Append a slash to the end of the spectra path if there isn't one
        if (self.options['spectraPath'] != '' and self.options['spectraPath'][-1] not in ['\\', '/']):
                self.options['spectraPath'] += '\\'
        self.options['eyecheck'] = (self.eyecheck.get() == 1)
        if (self.options['eyecheck'] or self.sncut.get() == ''):
            self.options['sncut'] = None
        else:
            self.options['sncut'] = float(self.sncut.get())
        
        self.root.destroy()

        main(self.options)

def startCmd(options):
    """
    startCmd(options)

    Description:
        This provides command line inputs for the user
        to enter options. It will only ask questions
        about options the user has not already specified
        at run time. This will then pass the updated
        options to the main function.

    Inputs:
        options: A dict containing the options the
            user can specify. These may already
            have default values if they were
            provided on the command line.
    """

    ##
    # If the input options were not provided on the command line at
    # execution, we need to ask for them here.
    #

    # Get the input filename if one was not provided
    if options['infile'] is None:
        while True:
            options['infile'] = input('Please enter the filename which contains the spectra list: ')
            infileExt = options['infile'][-4:]
            if infileExt[0] == '.' and infileExt[1:] != 'txt':
                print('The input file must be a text file.', flush = True)
                continue
            if not os.path.isfile(options['infile']+'.txt'*(options['infile'][-4:] != '.txt')):
                print('The input file cannot be found.', flush = True)
                continue
            break
    # Append a .txt extension to the filename if none was provided
    options['infile'] += '.txt'*(options['infile'][-4:] != '.txt')

    # Ask user if they want to change the results file and what to use if they do.
    if options['outfile'] == 'PyHammerResults.csv':
        ans = input('The results file is set to PyHammerResults.csv. Do you want to change it? (y/n): ')
        if ans.lower() == 'y':
            while True:
                options['outfile'] = input('Please enter the filename for the results file: ')
                outfileExt[0] = options['outfile'][-4:]
                if outfileExt[0] == '.' and outfileExt[1:] != 'csv':
                    print('The output file must be a csv file.', flush = True)
                    continue
                break
    # Append a .csv extension to the filename if none was provided
    options['outfile'] += '.csv'*(options['outfile'][-4:] != '.csv')

    # Ask user if they want to change the reject file and what to use if they do.
    if options['rejectfile'] == 'RejectSpectra.csv':
        ans = input('The reject file is set to RejectSpectra.csv. Do you want to change it? (y/n): ')
        if ans.lower() == 'y':
            while True:
                options['rejectfile'] = input('Please enter the filename for the reject file: ')
                rejectExt[0] = options['rejectfile'][-4:]
                if rejectExt[0] == '.' and rejectExt[1:] != 'csv':
                    print('The reject file must be a csv file.', flush = True)
                    continue
                break
    # Append a .csv extension to the filename if none was provided
    options['rejectfile'] += '.csv'*(options['rejectfile'][-4:] != '.csv')

    # Check whether the input file list contains the full path if
    # the user didn't already specify.
    if options['fullPath'] is None:
        ans = input('Does your input list give the full path to each spectrum? (y/n): ')
        if ans.lower() == 'y':
            options['fullPath'] = True
            options['spectraPath'] = ''
        else:
            options['fullPath'] = False
            while True:
                options['spectraPath'] = input('Enter the necessary path for each file: ')
                if not os.path.isdir(options['spectraPath']):
                    print('The path provided is not a valid directory.', flush = True)
                    continue
                break
            # Append a slash to the end of the spectra path, if there isn't one
            if options['spectraPath'][-1] not in ['\\', '/']:
                options['spectraPath'] += '\\'

    # Asks the user if they want to skip the auto-classifying and go straight
    # to checking by eye, if they have not already specified.
    if (options['eyecheck'] is None):
        ans = input('Do you want to skip straight to eye-checking? (y/n): ')
        options['eyecheck'] = (ans.lower() == 'y')

    # Asks the user if they want to apply a S/N cut when classifying the spectra.
    # This only applies if they chose not to skip the auto-classification
    if (options['eyecheck'] == False and options['sncut'] is None):
        ans = input('Do you want to supply a S/N cut when auto-classifying? (y/n): ')
        if ans.lower() == 'y':
            while True:
                ans = input('Choose a S/N cutoff (~3-5 recommended): ')
                try:
                    options['sncut'] = float(ans)
                    break
                except Error as e:
                    print(str(e), flush = True)

    # Now that all the options have been set, let's get started
    main(options)

if (__name__ == "__main__"):

    thisDir = os.path.split(__file__)[0]

    # Check if this is the first time this code has been executed by looking
    # for the runbefore file in the resources folder
    if not os.path.isfile(os.path.join(thisDir, 'resources', 'runbefore')):
        # The file doesn't exist. Let's create it and display the welcome message
        f = open(os.path.join(thisDir, 'resources', 'runbefore'), 'w')
        f.close()
        print('Welcome to PyHammer, a tool for spectral classification!\n'
              'First time users should run this program with the -h flag '
              'to learn more information.', flush = True)
    
    # Define default options
    options = {'infile': None, 'outfile': 'PyHammerResults.csv',
               'rejectfile': 'RejectSpectra.csv', 'fullPath': None,
               'spectraPath': None, 'eyecheck': None, 'sncut': None,
               'useGUI': None}
    
    ##
    # Check input conditions
    #

    opts, args = getopt.getopt(sys.argv[1:], 'hi:o:r:fp:es:cg',
                               ['help', 'infile=', 'outfile=', 'rejectfile=',
                                'full', 'path=', 'eyecheck', 'sncut',
                                'cmd', 'gui'])

    # First check if help is requested and options
    for opt, arg in opts:

        # Help option is chosen
        if (opt == '-h' or opt == '--help'):

            print(('\nWelcome to the PyHammer, a tool for spectral '
                   'classification.\n'
                   
                   '\nOptions:\n'
                   
                   '-c, --cmd\t\t\t'
                   'Flag to choose to run on the command line.\n'

                   '-e, --eyecheck\t\t'
                   'Flag indicating pyhammer should skip classifying\n'
                   '\t\t\t\t\tand go straight to checking the spectra by eye.\n'
                   
                   '-f, --full\t\t\t'
                   'Flag indicating the full path to the spectra is\n'
                   '\t\t\t\t\tprovided in the input file list.\n'
                   
                   '-g, --gui\t\t\t'
                   'Flag to choose to run using the gui.\n'
                   
                   '-i, --infile\t\t'
                   'The full path to the input file or the name, if it\n'
                   '\t\t\t\t\tis in the pyhammer folder. If nothing is\n'
                   '\t\t\t\t\tprovided, it will be asked for later.\n'
                   
                   '-o, --outfile\t\t'
                   'The full path to the output file or a filename\n'
                   '\t\t\t\t\twhich outputs to the pyhammer folder. If nothing is\n'
                   '\t\t\t\t\tprovided, the default pyhammerResults.csv will be\n'
                   '\t\t\t\t\tcreated in the pyhammer folder.\n'

                   '-p, --path\t\t\t'
                   'The full path to the spectra. This is only necessary\n'
                   '\t\t\t\t\tif the input file list does not prepend the path to\n'
                   '\t\t\t\t\tthe spectra filenames.\n'
                   
                   '-r, --rejectfile\t'
                   'The full path to the file where reject spectra will\n'
                   '\t\t\t\t\tbe listed or a filename which outputs to the\n'
                   '\t\t\t\t\tpyhammer folder . If nothing is provided, the\n'
                   '\t\t\t\t\tdefault rejectSpectra.csv will be created in the\n'
                   '\t\t\t\t\tpyhammer folder.\n'

                   '-s, --sncut\t\t\t'
                   'The S/N necessary before a spectra will be classified.\n'
                   '\t\t\t\t\tA signal to noise of ~3-5 per pixel is recommended.\n'

                   '\nExample:\n'
                   'python pyhammer.py -g -f -s 3 -i C:/Path/To/File/inputFile.txt -o'
                   'C:/Path/To/File/outputFile.csv -r C:/Path/To/File/rejectFile.csv\n').expandtabs(4),
                  flush = True)
            sys.exit(0)

        # User provided input file listing spectra
        if (opt == '-i' or opt == '--infile'):
            options['infile'] = arg

        # User provided output file for spectra classification
        if (opt == '-o' or opt == '--outfile'):
            options['outfile'] = arg

        # User provided output file for reject spectra
        if (opt == '-r' or opt == '--rejectfile'):
            options['rejectfile'] = arg

        # User indicated that the full path to the spectra is in the
        # input file list
        if (opt == '-f' or opt == '--full'):
            if (options['fullPath'] is not None):
                sys.exit('Cannot supply -f and -p at the same time. Use -h for more info.')
            else:
                options['fullPath'] = True
                options['spectraPath'] = ''

        # User provided a path to prepend to the spectra file names
        if (opt == '-p' or opt == '--path'):
            if (options['fullPath'] is not None):
                sys.exit('Cannot supply -f and -p at the same time. Use -h for more info.')
            else:
                options['fullPath'] = False
                options['spectraPath'] = arg
                # Append a slash to the end if there isn't one
                if (options['spectraPath'][-1] not in ['\\', '/']):
                    options['spectraPath'] += '\\'
            
        # User indicated they want to skip to the eyecheck
        if (opt == '-e' or opt == '--eyecheck'):
            if (options['sncut'] is not None):
                sys.exit('Flag -s is unnecessary when -e is provided. Use -h for more info.')
            else:
                options['eyecheck'] = True

        # User indicates they want a S/N cut to be applied
        if (opt == '-s' or opt == '--sncut'):
            if (options['eyecheck'] == True):
                sys.exit('Flag -s is unnecessary when -e is provided. Use -h for more info.')
            else:
                options['eyecheck'] = False
                options['sncut'] = arg

        # Command line interface is requested.
        if (opt == '-c' or opt == '--cmd'):
            if (options['useGUI'] is not None):
                sys.exit('Cannot supply -c and -g at the same time. Use -h for more info.')
            else:
                options['useGUI'] = False
        
        # GUI interface is requested.
        if (opt == '-g' or opt == '--gui'):
            if (options['useGUI'] is not None):
                sys.exit('Cannot supply -c and -g at the same time. Use -h for more info.')
            else:
                options['useGUI'] = True

    if options['useGUI'] == True:
        StartGUI(options)
    elif options['useGUI'] == False:
        startCmd(options)
    else:
        # If no interface is chosen, use the GUI by default
        options['useGUI'] = True
        StartGUI(options)

else:
    
    sys.exit("Do not import pyhammer. Run this script with the run command "
             "in the python environment, or by invoking with the python command "
             "on the command line. Use the -h flag for more information.")

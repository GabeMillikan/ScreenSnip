# The goal is to compile this program to an EXE
# which will not have a console window, however
# when i try to compile without the console, the
# program gets flagged as a virus... So for now,
# just print:
print("Eventually this window won't be here")
'''
    IMPORTS
'''

# Screenshot and windows util
import ctypes
import mss
import numpy as np
import PIL
import os
screencap = mss.mss()

def screenshotRegion(screenRegion):
    return np.asarray(screencap.grab(screenRegion))

# GUI
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import math # ceil, floor

# OCR
import pytesseract.pytesseract as tesseract
import pathlib
import threading

# setup Tesseract paths
myDirectory = str(pathlib.Path(__file__).parent.absolute())
tesseractDirectory = myDirectory + r"\TESSERACT"
tessdataDirectory = myDirectory + r"\TESSDATA"

tesseract.tesseract_cmd = tesseractDirectory + r"\tesseract.exe"
tessdataConfig = r'--tessdata-dir "%s"' % tessdataDirectory

def getTextFromImg(img, timeout = 3, language = 'eng'):
    return tesseract.image_to_string(img, timeout = timeout, lang = language, config = tessdataConfig)

'''
    UTILS
'''
def getVirturalDesktopDimensions():
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics
    SM_XVIRTUALSCREEN = 76 # LEFTMOST POSITION (not always 0)
    SM_YVIRTUALSCREEN = 77 # TOPMOST POSITION  (not always 0)
    
    SM_CXVIRTUALSCREEN = 78 # WIDTH (of all monitors)
    SM_CYVIRTUALSCREEN = 79 # HEIGHT (of all monitors)
    
    
    # https://docs.microsoft.com/en-us/windows/win32/gdi/multiple-monitor-system-metrics
    return {
        "left": ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        "top": ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        "width": ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        "height": ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    }

'''
    Screen region selector
'''
class screenRegionPromptWidget(QMainWindow):
    active = False
    mouseDownPoint = (0, 0)
    mouseCurrentPoint = (0, 0)
    mouseUpPoint = (0, 0)
    desktop = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    callback = None
    
    
    def __init__(self, *args, **kwargs):
        super(screenRegionPromptWidget, self).__init__(*args, **kwargs)
        
        # invisible background
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # "+" cursor
        self.setCursor(QCursor(Qt.CrossCursor))
        
        # get size of all monitors
        self.desktop = getVirturalDesktopDimensions()
        
        # resize window and repaint
        self.initUI()
    
    def initUI(self):
        self.resetWindow()
        self.repaint()
    
    '''
        Event handlers
    '''
    def moveEvent(self, event):
        # The window was moved, put it in the top left, and ignore the event
        self.resetWindow()
        event.ignore()
    
    
    def mousePressEvent(self, event):
        if self.active:
            self.mouseDownPoint = (event.x(), event.y())
        
    def mouseMoveEvent(self, event):
        if self.active and self.mouseDownPoint is not None:
            self.mouseCurrentPoint = (event.x(), event.y())
            self.repaint()
    
    def mouseReleaseEvent(self, event):
        if self.active and self.mouseDownPoint is not None:
            # we just finished a screenshot
            self.mouseUpPoint = (event.x(), event.y())
            self.complete()
    
    def paintEvent(self, event):
        if not self.active:
            return
        
        painter = QPainter(self)
        
        translucentWhite = QColor(255, 255, 255, 127)
        backgroundBrush = QBrush(translucentWhite)
        if self.mouseDownPoint is None: # Fill the whole screen with white
            painter.fillRect(QRect(0, 0, self.desktop['width'], self.desktop['height']), backgroundBrush)
        else:
            '''
            Instead of drawing a single large rectangle then "erasing" the screenshot region,
            draw 4 rectangles around the region
            
            +-----------+------------+-------+
            |           |     (2)    |       |
            |           |            |       |
            |           |############|       |
            |    (1)    |## region ##|  (3)  |
            |           |############|       |
            |           |            |       |
            |           |     (4)    |       |
            +-----------+------------+-------+
            '''
            
            # Region:
            region = self.regionFromTwoPoints(self.mouseDownPoint, self.mouseCurrentPoint)
            region['right'] = region['left'] + region['width']
            region['bottom'] = region['top'] + region['height']
            # Rect (1)
            painter.fillRect(QRect(0, 0, region['left'], self.desktop['height']), backgroundBrush)
            # Rect (2)
            painter.fillRect(QRect(region['left'], 0, region['width'], region['top']), backgroundBrush)
            # Rect (3)
            painter.fillRect(QRect(region['left'] + region["width"], 0, self.desktop['width'] - region['right'], self.desktop['height']), backgroundBrush)
            # Rect (4)
            painter.fillRect(QRect(region['left'], region['bottom'], region['width'], self.desktop['height'] - region['bottom']), backgroundBrush)
            
            # Now draw a red outline
            painter.setPen(QPen(QColor(255, 0, 0, 255), 1, Qt.SolidLine))
            painter.drawRect(region['left'], region['top'], region['width'], region['height'])
    
    def closeEvent(self, event):
        if self.active:
            self.complete()
        else:
            event.accept()
    
    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if self.active and not self.isActiveWindow():
                # make the user complete this screenshot weather they like it or not, lol
                self.raise_()
                self.activateWindow()
    
    '''
        Custom functions
    '''
    def reset(self):
        self.mouseDownPoint = None
        self.mouseUpPoint = None
        self.active = False
        self.callback = None
        self.initUI()
    
    def promptForRegion(self, callback = None):
        self.reset()
        self.active = True
        self.callback = callback
        self.show()
    
    def regionFromTwoPoints(self, a, b):
        x1, x2 = min(a[0], b[0]), max(a[0], b[0])
        y1, y2 = min(a[1], b[1]), max(a[1], b[1])
        w, h = max(1, x2-x1), max(1, y2-y1)
        return {"left": x1, "top": y1, "width": w, "height": h}
    
    def complete(self):
        if self.active and self.mouseDownPoint is not None and self.mouseUpPoint is not None:
            region = self.regionFromTwoPoints(self.mouseDownPoint, self.mouseUpPoint)
            callback = self.callback
            self.reset()
            self.hide()
            if callback:
                callback(region)
        else: # Failed / user canceled
            callback = self.callback
            self.reset()
            self.hide()
            if callback:
                callback(None)
    
    '''
        GUI utils
    '''
    def resetWindow(self):
        self.move(self.desktop['left'], self.desktop['top'])
        self.setFixedSize(self.desktop['width'], self.desktop['height'])

'''
    OCR Output window
'''
outputWindow_CSS = '''
QMainWindow{
    background-color: rgb(30, 30, 30);
}

#statusLabel{
    color: white;
}

QPlainTextEdit{
    background-color: rgb(70, 70, 70);
    color: white;
}
'''
class outputWindowWidget(QMainWindow):
    ocrStatusChangeSignal = pyqtSignal(int, int, str)
    userCanceledOperation = False
    die = False
    
    def __init__(self, *args, **kwargs):
        super(outputWindowWidget, self).__init__(*args, **kwargs)
        self.setWindowTitle("Output")
        self.setStyleSheet(outputWindow_CSS)
        
        self.ocrResult = QPlainTextEdit(self, objectName = "ocrResult")
        self.ocrResult.setPlaceholderText("Loading...")
        self.ocrResult.setFont(QFont("Consolas", 14, 10, False))
        
        self.statusLabel = QLabel("Scanning image for text...", self, objectName = "statusLabel")
        self.statusLabel.setAlignment(Qt.AlignRight)
        
        self.setMinimumSize(16 * 30, 9 * 30)
        self.resize(16 * 50, 9 * 50)
        
        self.ocrStatusChangeSignal.connect(self.ocrStatusChange)
    
    def sizeUI(self):
        self.ocrResult.move(5, 5)
        self.ocrResult.setFixedSize(self.width() - 10, self.height() - 25)
        
        self.statusLabel.move(5, self.height() - 18)
        self.statusLabel.setFixedSize(self.width() - 10, 15)
    
    def resizeEvent(self, event):   
        self.sizeUI()
    
    def ocrStatusChange(self, id, status, data):
        if status == OCRSTATUS_BEGIN:
            language = data
            self.statusLabel.setText("Scanning image for (%s) text..." % str(language))
            self.ocrResult.setPlainText("")
            self.ocrResult.setPlaceholderText("Scanning...")
            self.userCanceledOperation = False
            self.show()
            self.raise_()
            self.activateWindow()
        elif self.userCanceledOperation:
            return
        elif status == OCRSTATUS_TIMEOUT:
            err = data
            self.statusLabel.setText("Processing timed out. Did you select the right language?")
            self.ocrResult.setPlaceholderText("Timeout error... Make sure you have the right language selected, and your image is clearly legible!")
        elif status == OCRSTATUS_ERROR:
            err = data
            self.statusLabel.setText("Unknown Error [%s]. Try reinstalling?" % str(err))
            self.ocrResult.setPlaceholderText("Unknown error: %s\n\nTry uninstalling and reinstalling this program." % str(err))
        elif status == OCRSTATUS_FINISH:
            text = data
            self.statusLabel.setText("Scan completed! Found %d characters" % len(text))
            self.ocrResult.setPlaceholderText("Scan complete! If you're seeing this, then there was nothing found.")
            self.ocrResult.setPlainText(text)
    
    def kill(self):
        self.die = True
        self.close()
    
    def closeEvent(self, event):
        if not self.die:
            event.ignore()
            self.hide()
            self.userCanceledOperation = True
        else:
            event.accept()

'''
    Main OCR window
'''
mainWindow_CSS = '''
QMainWindow{
    background-color: rgb(30, 30, 30);
}

#screenSnipButton{
    background-color: rgb(25, 200, 75);
    border-radius: 5px;
    color: white;
}

#screenSnipButton:hover{
    background-color: rgb(0, 100, 50);
}

#openImageButton{
    background-color: rgb(0, 100, 230);
    border-radius: 5px;
    color: white;
}

#openImageButton:hover{
    background-color: rgb(0, 50, 150);
}

#topbarItemsContainer{
    background-color: rgb(75, 75, 75);
    border-radius: 5px;
}

#basicButtonLabels{
    color: white;
}

#imagePreview{
    border: 1px solid white;
}

#ocrLanguageSelector{
    border-radius: 5px;
}
'''

supportedOCRLanguages = [
    {"code": "eng", "name": "English", "local": "English"},
    {"code": "spa", "name": "Spanish", "local": "Español"},
    {"code": "rus", "name": "Russian", "local": "русский"},
]

supportedOCRScripts = [
    {"code": "script/Latin", "name": "Latin", "alphabet": "abcdefg", "examples": ["English", "French", "Spanish"]},
    {"code": "script/Cyrillic", "name": "Cyrillic", "alphabet": "абвгдеж", "examples": ["Russian", "Ukrainian", "Bulgarian"]},
    {"code": "script/Arabic", "name": "Arabic", "alphabet": "وهنملك", "examples": ["Iraqi", "Egyptian", "Moroccan"]},
]

OCRSTATUS_BEGIN = 0
OCRSTATUS_ERROR = 1
OCRSTATUS_TIMEOUT = 2
OCRSTATUS_FINISH = 3
class mainWindowWidget(QMainWindow):
    currentScanID = 0 # increases with every Tesseract call
    image_source = None
    currentOCRSourceLanguageIndex = 0
    lastOpenedDirectory = os.path.expanduser("~\\Pictures")

    def __init__(self, *args, **kwargs):
        super(mainWindowWidget, self).__init__(*args, **kwargs)
        self.setWindowTitle("Tesseract")
        
        windowWidth_noImage = 6 + 100 + 3 + 100 + 6
        self.setFixedSize(windowWidth_noImage, 50 + 40)
        
        self.screenRegionWindow = screenRegionPromptWidget()
        
        self.topbarItems = QLabel(self, objectName = "topbarItemsContainer")
        self.topbarItems.setFixedSize(windowWidth_noImage - 6, 50 - 6)
        self.topbarItems.move(3, 3)
        
        self.screenSnipButton = QPushButton("NEW", self.topbarItems, objectName = "screenSnipButton")
        self.screenSnipButton.clicked.connect(self.newSnipPressed)
        self.screenSnipButton.setFont(QFont("Gotham", 20, 1000, False))
        self.screenSnipButton.setFixedSize(100, 50 - 12)
        self.screenSnipButton.move(3, 3)
        
        self.openImageButton = QPushButton("OPEN", self.topbarItems, objectName = "openImageButton")
        self.openImageButton.clicked.connect(self.openImagePressed)
        self.openImageButton.setFont(QFont("Gotham", 20, 1000, False))
        self.openImageButton.setFixedSize(100, 50 - 12)
        self.openImageButton.move(3 + 100 + 3, 3)
        
        self.OCRLanguageSelector = QComboBox(self.topbarItems, objectName = "ocrLanguageSelector")
        self.OCRLanguageSelector.setFont(QFont("Consolas", 10, 1000, False))
        self.OCRLanguageSelector.setFixedSize(200, 50 - 12)
        self.OCRLanguageSelector.move(3 + 100 + 3 + 100 + 3, 3)
        self.OCRLanguageSelector.hide()
        for lang in supportedOCRLanguages:
            self.OCRLanguageSelector.addItem("%s (%s)" % (lang['name'], lang['local']))
        self.OCRLanguageSelector.insertSeparator(len(supportedOCRLanguages))
        for lang in supportedOCRScripts:
            self.OCRLanguageSelector.addItem("%s Script (%s)" % (lang['name'], lang['alphabet']))
        self.OCRLanguageSelector.currentIndexChanged.connect(self.OCRLangChange)
        
        self.basicButtonLabels = QLabel("NEW: Take a screenshot\nOPEN: Open a file", self, objectName = "basicButtonLabels")
        self.basicButtonLabels.setFont(QFont("Gotham", 11, 100, False))
        self.basicButtonLabels.setFixedSize(97 + 3 + 97, 40)
        self.basicButtonLabels.move(6, 50)
        
        self.imagePreview = QLabel("", self, objectName = "imagePreview")
        self.imagePreview.hide()
        
        self.outputWindow = outputWindowWidget()
        self.outputWindow.hide()
        
        self.setStyleSheet(mainWindow_CSS)
    
    def newSnipPressed(self):
        self.hide()
        self.outputWindow.close() # wont actually close
        self.screenRegionWindow.promptForRegion(callback = self.gotScreenRegionForSnip)
    
    def openImagePressed(self):
        dialogTitle = "Open Image"
        openInDirectory = self.lastOpenedDirectory
        acceptedFiles = "Image files (*.png *.jpeg *jpg)"
        
        (fname, x) = QFileDialog.getOpenFileName(self, dialogTitle, openInDirectory, acceptedFiles)
        if x == '':
            return
        else:
            img = None
            try:
                self.lastOpenedDirectory = str(pathlib.Path(fname).parent)
                
                pic = PIL.Image.open(fname)
                
                img = np.array(pic)
                if img.shape[-1] == 4: # drop alpha channel
                    img = img[:,:,:3]
                
            except BaseException as e:
                print("Failed to open image: %s" % str(e))
            
            self.newImage(img)
    
    def startOCR(self, image, id, language):
        text = None
        
        try:
            text = getTextFromImg(image, timeout = 120, language = language['code'])
        except BaseException as e:
            if "Tesseract process timeout" in str(e):
                # Tell output that a we timed out
                # (only if no new images have come in)
                if id != self.currentScanID:
                    return
                return self.outputWindow.ocrStatusChangeSignal.emit(id, OCRSTATUS_TIMEOUT, str(e))
            else:
                # Tell output that a we errored
                # (only if no new images have come in)
                if id != self.currentScanID:
                    return
                return self.outputWindow.ocrStatusChangeSignal.emit(id, OCRSTATUS_ERROR, str(e))
        
        # Tell output that a we are done!
        # (only if no new images have come in)
        if id != self.currentScanID:
            return
        if text is None:
            text = ""
        return self.outputWindow.ocrStatusChangeSignal.emit(id, OCRSTATUS_FINISH, str(text))
    
    def gotScreenRegionForSnip(self, region):
        if region is None:
            print("Canceled screen snip")
            self.show()
        else:
            img = screenshotRegion(region)
            self.show()
            
            if img.shape[-1] == 4: # drop alpha channel
                img = img[:,:,:3]
            img = img[:,:,::-1] # BGR -> RGB
            
            self.newImage(img)
    
    def newImage(self, img):
        self.image_source = img
        
        self.newOCR()
    
    def OCRLangChange(self, newIndex):
        if newIndex == self.currentOCRSourceLanguageIndex:
            return
        self.currentOCRSourceLanguageIndex = newIndex
        self.newOCR()
        
    def newOCR(self):
        if self.image_source is None: # we need an image
            return
        
        self.currentScanID += 1
        if self.currentScanID == 1: # the first time, setup our window
            self.basicButtonLabels.hide()
            self.imagePreview.show()
            self.OCRLanguageSelector.show()
            self.topbarItems.setFixedSize(3 + 100 + 3 + 100 + 3 + 200 + 3, 50 - 6)
        
        language = None
        if self.currentOCRSourceLanguageIndex < len(supportedOCRLanguages):
            language = supportedOCRLanguages[self.currentOCRSourceLanguageIndex]
        else:
            language = supportedOCRScripts[self.currentOCRSourceLanguageIndex - len(supportedOCRLanguages) - 1]
        
        # show image
        h, w, ch = self.image_source.shape
        qimg = QImage(self.image_source.data.tobytes(), w, h, ch * w, QImage.Format_RGB888)
        self.imagePreview.setPixmap(QPixmap.fromImage(qimg))
        self.imagePreview.setFixedSize(w, h)
        
        # resize main window
        topbarWidth = 3 + 100 + 3 + 100 + 3 + 200 + 3
        imageWidth = w
        imagePosition = 3
        topbarPosition = 3
        windowWidth = 100
        if topbarWidth == imageWidth:
            imagePosition = topbarPosition = 3
            windowWidth = 3 + topbarWidth + 3
        elif topbarWidth > imageWidth:
            topbarPosition = 3
            imagePosition = 3 + (topbarWidth - imageWidth)/2
            windowWidth = 3 + topbarWidth + 3
        else: #if topbarWidth < imageWidth:
            imagePosition = 3
            topbarPosition = 3 + (imageWidth - topbarWidth)/2
            windowWidth = 3 + imageWidth + 3
        
        self.imagePreview.move(math.floor(imagePosition), 50)
        self.topbarItems.move(math.floor(topbarPosition), 3)
        self.setFixedSize(math.ceil(windowWidth), 53 + h)
        
        # notify outputWindow to get ready, and begin OCR
        self.outputWindow.ocrStatusChangeSignal.emit(self.currentScanID, OCRSTATUS_BEGIN, language['name'])
        threading.Thread(target = self.startOCR, args = [self.image_source, self.currentScanID, language]).start()
    
    def closeEvent(self, event):
        # user pressed X on the main window, shutdown
        self.outputWindow.kill()
        self.screenRegionWindow.active = False
        self.screenRegionWindow.close()

if __name__ == "__main__":
    app = QApplication([])
    
    window = mainWindowWidget()
    window.show()
    
    app.exec_()
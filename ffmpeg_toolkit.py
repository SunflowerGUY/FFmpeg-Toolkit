import os
import sys
import json
import pathlib
import threading
import subprocess
from datetime import datetime

import customtkinter as ctk
from PIL import Image as PilImage

APP_VERSION = "1.0"
BUILD_DATE = "27 August 2026"


class FFmpegToolkit(ctk.CTk):
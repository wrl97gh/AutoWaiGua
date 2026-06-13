"""A collection of variables shared across multiple modules."""


#########################
#       Constants       #
#########################
RESOURCES_DIR = 'resources'


#################################
#       Global Variables        #
#################################
# The player's position relative to the minimap
player_pos = (0, 0)

# Describes whether the main bot loop is currently running or not
enabled = False

# If there is another player in the map, Auto Maple will purposely make random human-like mistakes
stage_fright = False

# Whether continuous siren alerts should be ignored without stopping the bot
ignore_siren_alerts = False

# Set to True (e.g. by a remote /stop command) to silence an active siren alert
alert_ack = False

# Represents the current shortest path that the bot is taking
path = []

# Portal locations on the minimap (relative coordinates), updated by Notifier
portal_positions = []

# Scales the portal UP-suppression zone; the bot shrinks it while approaching
# a rune so portals can't block a required climb
portal_lock_scale = 1.0


#############################
#       Shared Modules      #
#############################
# A Routine object that manages the 'machine code' of the current routine
routine = None

# Stores the Layout object associated with the current routine
layout = None

# Shares the main bot loop
bot = None

# Shares the video capture loop
capture = None

# Shares the keyboard listener
listener = None

# Shares the remote notification/control module
remote = None

# Shares the gui to all modules
gui = None

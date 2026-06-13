<h1 align="center">
  Auto Maple
</h1>

Auto Maple is an intelligent Python AI that plays MapleStory, a 2D side-scrolling MMORPG, using simulated key presses, TensorFlow machine learning, OpenCV template matching, and other computer vision techniques.

Community-created resources, such as **command books** for each class and **routines** for each map, can be found in the **[resources repository](https://github.com/tanjeffreyz/auto-maple-resources)**.

<br>

<h2 align="center">
  Fork Additions
</h2>

<h3>
  GUI Resource Selection & Routine Editing
</h3>

<p>
The <b>Edit</b> page now keeps the active resources visible at the top of the window. Select a Command Book first, then choose one of its Routine CSV files from the adjacent dropdown. Both selectors also include a <b>Browse...</b> button for files outside the standard resource directories.
</p>

<p>
After editing Points or Commands, click <b>Save Routine</b> to write the changes directly back to the loaded CSV. A newly created Routine prompts for a filename on its first save, then subsequent saves update that same file. Loading and saving are disabled while the bot is running, and unsaved-change confirmation is preserved when switching resources.
</p>

<h3>
  GUI Minimap Layout Builder
</h3>

<p>
The old <b>Record layout</b> checkbox has been replaced by a dedicated <b>Layout</b> page. First select a Command Book and Routine on the Edit page, then choose one of the following sources:
</p>

<ul>
  <li><b>Live minimap</b> &mdash; sample the running game for a chosen duration. Move around the map and pause for about one second on each platform.</li>
  <li><b>Saved screenshots</b> &mdash; select multiple full-frame screenshots from the same map.</li>
</ul>

<p>
Use <b>Preview only</b> for the first run. The preview marks detected platforms in red and generated pathfinding nodes in blue. When the result looks correct, disable Preview only and build again to save it under <code>resources/layouts/&lt;command-book&gt;/&lt;routine-name&gt;</code>. New nodes are merged into an existing Layout instead of replacing it. The same engine remains available from the command line:
</p>

<pre><code># Offline screenshots:
python3 tools/build_layout.py v260 --frames 'assets/debug/rune/2026MMDD_*/*_01_frame.png' --dry-run

# Live sampling for 90 seconds:
python3 tools/build_layout.py v260 --live --duration 90</code></pre>

<h3>
  Rune Navigation & Portal Guard
</h3>

<p>
Portals near farming spots can swallow accidental UP presses and change maps. Auto Maple tracks portal icons on the minimap and suppresses synthetic UP presses near them, including releasing an already-held UP. Detected portals are remembered for 120 seconds so the player's dot covering an icon does not disable protection.
</p>

<p>
Rune navigation now handles the conflict between climbing and portal protection. While approaching a rune, the portal suppression zone is temporarily reduced and restored afterward. The bot creates a horizontal approach point beside the rune, randomly tries the left or right side when both are available, switches sides after a failed attempt, and automatically approaches from the only safe side near a map edge.
</p>

<p>
Tune or disable the normal portal guard per Routine with <code>$, portal_lock_radius, 0.03</code>; use <code>0</code> for routines that intentionally enter portals.
</p>

<h3>
  Rune Dataset, Training & Detection Engines
</h3>

<p>
Every rune solve attempt can save screenshots and metadata to <code>assets/rune_dataset/</code>. Configure screenshot collection, confirmation behavior, and the active engine under <b>Settings &rarr; Runes</b>.
</p>

<ul>
  <li><b>Label</b>: <code>python3 tools/rune_labeler.py</code> &mdash; label the four arrow directions and review collection progress with <code>--stats</code>.</li>
  <li><b>Evaluate</b>: <code>python3 tools/rune_eval.py</code> &mdash; compare exact-match accuracy, per-arrow accuracy, wrong entries, and latency.</li>
  <li><b>Train Detection 3</b>: <code>python3 tools/train_rune_cnn.py</code> &mdash; train the per-slot CNN from labeled sessions; use <code>--rebuild-cache</code> after adding labels.</li>
</ul>

<p>
Select <b>Detection 3 (CNN)</b> in Settings to use the newer batched four-slot classifier. It loads <code>assets/models/rune_arrow_cnn.keras</code> lazily and returns uncertain slots to the existing multi-frame voting flow. Detection 1 and Detection 2 remain available.
</p>

<h3>
  Remote Control & Emergency Stop (Telegram)
</h3>

<p>
Auto Maple can push alerts and screenshots to a Telegram chat and accept remote commands. Create a bot through <b>@BotFather</b>, paste its token into <b>Settings &rarr; Remote Control (Telegram)</b>, send the bot any message to discover your chat id, then use <b>Send test message</b> to verify the connection.
</p>

<ul>
  <li><code>/stop</code> &mdash; stop the bot and silence an active siren.</li>
  <li><code>/start</code> &mdash; recalibrate the minimap and resume.</li>
  <li><code>/status</code> &mdash; report state, Routine, position, rune status, and uptime.</li>
  <li><code>/screenshot</code> &mdash; send the current game frame.</li>
</ul>

<p>
Only the configured chat id is accepted. Commands sent while Auto Maple was offline are discarded during startup. The token is stored in plaintext under <code>.settings/remote</code>, which is gitignored and should not be shared.
</p>

<h3>
  Control-Break (Struggle) Auto-Escape
</h3>

<p>
When the left/right control-break QTE appears, Auto Maple detects the two arrow buttons at multiple scales, pauses normal bot key output, and alternates left/right with randomized timing until several settled frames confirm that the UI is gone. It saves a screenshot, sends a Telegram notification, and triggers the siren after a 15-second failure.
</p>

<p>
Regenerate changed UI templates with <code>python3 tools/make_struggle_templates.py "path/to/screenshot.png"</code>. Use <code>python3 tools/test_struggle_input.py</code> to verify that synthetic movement reaches the game.
</p>

<h3>
  Humanization & Safety
</h3>

<ul>
  <li>Buff, pet-feed, movement, attack, and rune-entry timings use bounded random jitter.</li>
  <li>The bot takes occasional 8&ndash;45 second breaks every 20&ndash;45 minutes, except during active rune handling.</li>
  <li>Other-player detection enables heavier <code>stage_fright</code> hesitation, plays a notification sound, and sends a Telegram alert.</li>
  <li>Black-screen, unsolved-rune, and failed-struggle alerts stop the bot and can include a screenshot.</li>
</ul>

<br>


<h2 align="center">
  Minimap
</h2>

<table align="center" border="0">
  <tr>
    <td>
Auto Maple uses <b>OpenCV template matching</b> to determine the bounds of the minimap as well as the various elements within it, allowing it to accurately track the player's in-game position. Layout files store map platforms in a <b>quadtree-based</b> object and can be generated from the fork's Layout page or loaded alongside an existing Routine. The Layout object uses the <b>A* search algorithm</b> on its stored points to calculate the shortest path from the player to any target location, which can dramatically improve the accuracy and speed at which routines are executed.
    </td>
    <td align="center" width="400px">
      <img align="center" src="https://user-images.githubusercontent.com/69165598/123177212-b16f0700-d439-11eb-8a21-8b414273f1e1.gif"/>
    </td>
  </tr>
</table>

<br>








<h2 align="center">
  Command Books
</h2>

<p align="center">
  <img src="https://user-images.githubusercontent.com/69165598/123372905-502e5d00-d539-11eb-81c2-46b8bbf929cc.gif" width="100%"/>
  <br>
  <sub>
    The above video shows Auto Maple consistently performing a mechanically advanced ability combination.
  </sub>
</p>
  
<table align="center" border="0">
  <tr>
    <td width="100%">
Designed with modularity in mind, Auto Maple can operate any character in the game as long as it is provided with a list of in-game actions, or a "command book". A command book is a Python file that contains multiple classes, one for each in-game ability, that tells the program what keys it should press and when to press them. Once a command book is imported, its classes are automatically compiled into a dictionary that Auto Maple can then use to interpret commands within routines. Commands have access to all of Auto Maple's global variables, which can allow them to actively change their behavior based on the player's position and the state of the game.
    </td>
  </tr>
</table>
  
<br>







<h2 align="center">
  Routines
</h2>

<table align="center" border="0">
  <tr>
    <td width="350px">
      <p align="center">
        <img src="https://user-images.githubusercontent.com/69165598/150469699-d8a94ab4-7d70-49c3-8736-a9018996f39a.png"/>
        <br>
        <sub>
          Click <a href="https://github.com/tanjeffreyz02/auto-maple/blob/f13d87c98e9344e0a4fa5c6f85ffb7e66860afc0/routines/dcup2.csv">here</a> to view the entire routine.
        </sub>
      </p>
    </td>
    <td>
A routine is a user-created CSV file that tells Auto Maple where to move and what commands to use at each location. A custom compiler within Auto Maple parses through the selected routine and converts it into a list of <code>Component</code> objects that can then be executed by the program. An error message is printed for every line that contains invalid parameters, and those lines are ignored during the conversion. 
<br><br>
Below is a summary of the most commonly used routine components:
<ul>
  <li>
    <b><code>Point</code></b> stores the commands directly below it and will execute them in that order once the character is within <code>move_tolerance</code> of the specified location. There are also a couple optional keyword arguments:
    <ul>
      <li>
        <code>adjust</code> fine-tunes the character's position to be within <code>adjust_tolerance</code> of the target location before executing any commands.
      </li>
      <li>
        <code>frequency</code> tells the Point how often to execute. If set to N, this Point will execute once every N iterations.
      </li>
      <li>
        <code>skip</code> tells the Point whether to run on the first iteration or not. If set to True and frequency is N, this Point will execute on the N-1th iteration.
      </li>
    </ul>
  </li>
  <li>
    <b><code>Label</code></b> acts as a reference point that can help organize the routine into sections as well as create loops.
  </li>
  <li>
    <b><code>Jump</code></b> jumps to the given label from anywhere in the routine.
  </li>
  <li>
    <b><code>Setting</code></b> updates the specified setting to the given value. It can be placed anywhere in the routine, so different parts of the same routine can have different settings. All editable settings can be found at the bottom of <a href="https://github.com/tanjeffreyz02/auto-maple/blob/v2/settings.py">settings.py</a>.
  </li>
</ul>
    </td>
  </tr>
</table>

<br>








<h2 align="center">
  Runes
</h2>

<p align="center">
  <img src="https://user-images.githubusercontent.com/69165598/123479558-f61fad00-d5b5-11eb-914c-8f002a96dd62.gif" width="100%"/>
</p>

<table align="center" border="0">
  <tr>
    <td width="100%">
Auto Maple has the ability to automatically solve "runes", or in-game arrow key puzzles. It first uses OpenCV's color filtration and <b>Canny edge detection</b> algorithms to isolate the arrow keys and reduce as much background noise as possible. Then, it runs multiple inferences on the preprocessed frames using a custom-trained <b>TensorFlow</b> model until two inferences agree. Because of this preprocessing, Auto Maple is extremely accurate at solving runes in all kinds of (often colorful and chaotic) environments.
    </td>
  </tr>
</table>


<br>









<h2 align="center">
  Video Demonstration
</h2>

<p align="center">
  <a href="https://youtu.be/iNj1CWW2--8?si=MA4n6EAHokI9FX8B"><b>Click below to watch the full video</b></a>
</p>

<p align="center">
  <a href="https://youtu.be/iNj1CWW2--8?si=MA4n6EAHokI9FX8B">
    <img src="https://user-images.githubusercontent.com/69165598/123308656-c5b61100-d4d8-11eb-99ac-c465665474b5.gif" width="600px"/>
  </a>
</p>

<br>



<h2 align="center">
  Setup
</h2>

<h3>
  macOS notes
</h3>

<p>
This fork includes macOS-compatible window capture, global hotkey tracking, and keyboard/mouse control. The default macOS start/stop hotkey is <code>F8</code> because Apple keyboards usually do not expose an <code>Insert</code> key. MapleStory still needs to be visible in a window whose title or owner contains <code>MapleStory</code>; if that window cannot be found, Auto Maple falls back to the primary screen area.
</p>

<ol>
  <li>
    Install Python 3.10 or newer.
  </li>
  <li>
    Install dependencies:
    <pre><code>python3 -m pip install -r requirements.txt</code></pre>
  </li>
  <li>
    Grant macOS permissions to the app that launches Auto Maple, such as Terminal, iTerm, or Codex:
    <ul>
      <li><b>System Settings → Privacy &amp; Security → Screen Recording</b></li>
      <li><b>System Settings → Privacy &amp; Security → Accessibility</b></li>
    </ul>
    Restart the launcher app after changing these permissions.
  </li>
  <li>
    Run Auto Maple:
    <pre><code>python3 main.py</code></pre>
  </li>
  <li>
    Optional: create a desktop launcher:
    <pre><code>python3 setup.py --stay</code></pre>
  </li>
</ol>

<h3>
  Windows notes
</h3>

<ol>
  <li>
    Download and install <a href="https://www.python.org/downloads/">Python3</a>.
  </li>
  <li>
    Download and install the latest version of <a href="https://developer.nvidia.com/cuda-downloads">CUDA Toolkit</a>.
  </li>
  <li>
    Download and install <a href="https://git-scm.com/download/win">Git</a>.
  </li>
  <li>
    Download and unzip the latest <a href="https://github.com/tanjeffreyz02/auto-maple/releases">Auto Maple release</a>.
  </li>
  <li>
    Download the <a href="https://drive.google.com/drive/folders/1SPdTNF4KZczoWyWTgfyTBRvLvy7WSGpu?usp=sharing">TensorFlow model</a> and unzip the "models" folder into Auto Maple's "assets" directory.
  </li>
  <li>
    Inside Auto Maple's main directory, open a command prompt and run:
    <pre><code>python -m pip install -r requirements.txt</code></pre>
  </li>
  <li>
    Lastly, create a desktop shortcut by running:
    <pre><code>python setup.py</code></pre>
    This shortcut uses absolute paths, so feel free to move it wherever you want. However, if you move Auto Maple's main directory, you will need to run <code>python setup.py</code> again to generate a new shortcut. To keep the command prompt open after Auto Maple closes, run the above command with the <code>--stay</code> flag.
  </li>
</ol>

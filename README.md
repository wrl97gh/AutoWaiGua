<h1 align="center">
  Auto Maple
</h1>

Auto Maple is an intelligent Python AI that plays MapleStory, a 2D side-scrolling MMORPG, using simulated key presses, TensorFlow machine learning, OpenCV template matching, and other computer vision techniques.

Community-created resources, such as **command books** for each class and **routines** for each map, can be found in the **[resources repository](https://github.com/tanjeffreyz/auto-maple-resources)**.

<br>


<h2 align="center">
  Minimap
</h2>

<table align="center" border="0">
  <tr>
    <td>
Auto Maple uses <b>OpenCV template matching</b> to determine the bounds of the minimap as well as the various elements within it, allowing it to accurately track the player's in-game position. If <code>record_layout</code> is set to <code>True</code>, Auto Maple will record the player's previous positions in a <b>quadtree-based</b> Layout object, which is periodically saved to a file in the "layouts" directory. Every time a new routine is loaded, its corresponding layout file, if it exists, will also be loaded. This Layout object uses the <b>A* search algorithm</b> on its stored points to calculate the shortest path from the player to any target location, which can dramatically improve the accuracy and speed at which routines are executed.
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
  Fork Additions
</h2>

<h3>
  Remote Control & Emergency Stop (Telegram)
</h3>

<p>
Auto Maple can push alerts to your phone and accept remote commands through a Telegram bot. Pushed events include: siren alerts (black screen, unsolved rune, failed struggle) with a screenshot, rune solve results, bot start/stop state changes, and other players appearing on the map.
</p>

<b>Setup:</b>
<ol>
  <li>
    In Telegram, message <b>@BotFather</b>, send <code>/newbot</code>, follow the prompts, and copy the bot token (looks like <code>1234567:ABC-xxxx</code>).
  </li>
  <li>
    Start Auto Maple, open <b>Settings &rarr; Remote Control (Telegram)</b>, paste the token, and click <b>Save</b>.
  </li>
  <li>
    Send any message to your new bot. The bot replies with your <b>chat id</b> (it is also printed in the Auto Maple console). Paste it into the <b>Chat id</b> field and click <b>Save</b>.
  </li>
  <li>
    Click <b>Send test message</b>. If your phone receives it, you are done.
  </li>
</ol>

<b>Commands</b> (only the configured chat id is obeyed; messages from anyone else are ignored):
<ul>
  <li><code>/stop</code> &mdash; emergency stop. Stops the bot and silences an active siren.</li>
  <li><code>/start</code> &mdash; recalibrates the minimap, then resumes the bot.</li>
  <li><code>/status</code> &mdash; current state, routine, player position, rune status, uptime.</li>
  <li><code>/screenshot</code> &mdash; sends the current game frame.</li>
</ul>

<p>
Notes: the token is stored in plaintext in <code>.settings/remote</code> (gitignored &mdash; do not share that file). Commands sent while Auto Maple was offline are discarded on startup, so a stale <code>/start</code> can never enable the bot unexpectedly.
</p>

<h3>
  Control-Break (Struggle) Auto-Escape
</h3>

<p>
When a monster grabs the character and the left/right arrow QTE appears, Auto Maple detects the arrow-button UI (both buttons, multiple scales, tolerant of effects covering one button) and mashes left/right at a human-like pace (~10 presses/s with jitter and hesitations) until the UI disappears. The bot's own key output is paused during the struggle so held movement keys cannot corrupt the input. Each trigger saves a screenshot to <code>assets/debug/struggle/</code> and pushes a Telegram notification; after 15 seconds without escaping, the siren alert fires.
</p>

<p>
The detection templates live at <code>assets/struggle_left_template.png</code> and <code>assets/struggle_right_template.png</code>. If the game UI changes, regenerate them from a screenshot showing both buttons:
<pre><code>python3 tools/make_struggle_templates.py "path/to/screenshot.png"</code></pre>
To verify that synthetic input reaches the game, run <code>python3 tools/test_struggle_input.py</code> and watch the character shuffle left/right.
</p>

<h3>
  Portal Guard
</h3>

<p>
Portals near farming spots can swallow accidental UP presses and change maps. Auto Maple now tracks portal icons on the minimap (template: <code>assets/portal_template.png</code>) and suppresses synthetic UP presses &mdash; including force-releasing an already-held UP &mdash; whenever the player is within <code>portal_lock_radius</code> (default <code>0.05</code>) of a portal. Detected portals are remembered for 120 seconds, so the player's own dot covering the icon while standing on a portal does not break the guard.
</p>

<p>
Tune or disable it per routine with a Setting line in the CSV: <code>$, portal_lock_radius, 0.03</code> (use <code>0</code> for routines that intentionally take portals).
</p>

<h3>
  Rune Dataset, Labeling & Engine Evaluation
</h3>

<p>
Every rune solve attempt saves its screenshots and metadata (engine, prediction, whether the panel disappeared after entry) to <code>assets/rune_dataset/</code> &mdash; toggle in <b>Settings &rarr; Runes</b>. This builds a ground-truth corpus over time:
</p>

<ul>
  <li>
    <b>Label</b>: <code>python3 tools/rune_labeler.py</code> &mdash; press the four arrow keys, then Enter to save and jump to the next unlabeled session (<code>s</code> skip, <code>f</code> full frame, <code>--stats</code> for progress). Legacy debug sessions under <code>assets/debug/rune/</code> are picked up too.
  </li>
  <li>
    <b>Evaluate</b>: <code>python3 tools/rune_eval.py</code> &mdash; scores both detection engines against the labels (exact match, wrong-entry rate, per-arrow accuracy, latency). Use <code>--engines</code>, <code>--cpu</code>, <code>--roots</code> to narrow the run.
  </li>
</ul>

<h3>
  Humanization
</h3>

<ul>
  <li>Buff and pet-feed cooldowns re-fire with random late-side jitter instead of exact periods.</li>
  <li>Buff salvos use randomized gaps between casts; key hold times are non-zero with jitter.</li>
  <li>Movement and attacks occasionally hesitate; fixed combo delays carry narrow random jitter.</li>
  <li>The bot idles for 8&ndash;45 seconds every 20&ndash;45 minutes (skipped while a rune is active).</li>
  <li>Other-player detection is active again: while anyone else is on the map, the heavier <code>stage_fright</code> hesitation kicks in, a ding plays, and a Telegram notification is sent.</li>
</ul>

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

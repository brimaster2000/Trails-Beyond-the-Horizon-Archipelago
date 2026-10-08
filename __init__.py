# The first thing you should make for your world is an archipelago.json manifest file.
# You can reference APQuest's, but you should change the "game" field (obviously),
# and you should also change the "minimum_ap_version" - probably to the current value of Utils.__version__.

# Apart from the regular apworld code that allows generating multiworld seeds with your game,
# your apworld might have other "components" that should be launchable from the Archipelago Launcher.
# You can ignore this for now. If you are specifically interested in components, you can read components.py.

# The main thing we do in our __init__.py is importing our world class from our world.py to initialize it.
# Obviously, this world class needs to exist first. For this, read world.py.
from .world import trailsbthWorld as trailsbthWorld

from worlds.LauncherComponents import Component, components, launch as launch_component, Type, icon_paths
from Utils import local_path
from typing import List, Dict, TextIO

def launch_client(*args: str):
    """Launch a Trails Beyond the Horizon client instance"""
    from worlds.beyondthehorizon.Client import launch

    launch_component(launch, name="TBTHClient", args=args)

components.append(Component("Trails Beyond the Horizon Client", "TBTHClient", func=launch_client, component_type=Type.CLIENT, icon='van'))

icon_paths['van'] = local_path('data', 'van.png')
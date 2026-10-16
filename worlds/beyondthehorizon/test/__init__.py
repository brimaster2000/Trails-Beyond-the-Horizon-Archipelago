from test.bases import WorldTestBase

from ..world import trailsbthWorld


class TrailsBTHTestBase(WorldTestBase):
    game = "Trails Beyond the Horizon"
    world: trailsbthWorld

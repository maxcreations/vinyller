"""
Vinyller — Set of random greetings
Copyright (C) 2026 Maxim Moshkin
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import random

from src.utils.utils_translator import translate


def get_random_greeting():
    """
    Return a random greeting message.
    """
    greetings = [
        translate("Time to listen to something new?"),
        translate("High time for something spontaneous!"),
        translate("High time for something fresh!"),
        translate("Ready to catch the Wave?"),
        translate("Ready to jazz it up?"),
        translate("Ready to feel the groove?"),
        translate("Ready to turn it up?"),
        translate("It's time to rock and roll!"),
        translate("What time is it? Looks like music time!"),
        translate("What year is it? Doesn't matter — music is timeless!"),
        translate("What's on your sound radar today?"),
        translate("Listen to what Vinyller has prepared for you!"),
        translate("Time to spin some records!"),
        translate("Time to shake the dust off your speakers!"),
        translate("Shall we listen to some random music?"),
        translate("Ready to unearth some sonic gold?"),
        translate("Who knows what you might find today?"),
        translate("Ready to expand your sound horizons?"),
        translate("Let's go off the beaten track!"),
        translate("Tuning into a random frequency..."),
        translate("Let's put the volume... on the top shelf!"),
        translate("Let's turn on the curiosity!"),
        translate("Just flip the record!"),
        translate("Bass check, mic check, vibe check. Let's go!"),
    ]
    return random.choice(greetings)


def get_random_waiting():
    """
    Return a random waiting message for loading collections.
    """
    waiting_text = [
        translate("Whoa! You've collected a lot of records! Please hang tight while your albums are loading..."),
        translate("Whoa! You’ve got a whole collection of masterpieces here. Make yourself comfortable while we arrange your records on the shelves..."),
        translate("Wow, that’s a lot of vinyl! We need a moment to dust off every cover. Loading..."),
        translate("Someone clearly loves music! We’re halfway to the finale, don’t touch that dial..."),
        translate("Your collection is longer than a progressive rock solo. Loading your albums, hang tight..."),
        translate("Looks like we found a true fan! Sorting through your treasures, this will only take a moment..."),
        translate("An impressive selection! We are preparing your albums for listening. Stay with us..."),
        translate("So much music in one place! The loading magic has begun, everything will be ready soon..."),
        translate("Whoa, look at all these finds! We are carefully loading your media library. Just a second of your patience..."),
        translate("Bass check, mic check, vibe check, scroll check..."),
        translate("Your collection is longer than a 70s drum solo! Hang tight, we’re nearly finished loading..."),
        translate("We’re gonna need a bigger shelf for all this! Sorting through your treasures now..."),
        translate("Look at all those gems! Polishing the covers and lining them up for you. One moment..."),
    ]
    return random.choice(waiting_text)
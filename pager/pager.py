import sys
import os
import re
import math
from datetime import datetime

import gtk
import gobject
from Xlib import X, display, error, Xatom, Xutil
import Xlib.protocol.event


class PagerFactory:

    def get_pager(self, display, screen, root):
        '''Auto-detects pager to use.'''
        pager = None

        grid = root.get_full_property(
            display.get_atom('_NET_DESKTOP_LAYOUT'),
            0)
        size = root.get_full_property(
            display.get_atom("_NET_DESKTOP_GEOMETRY"),
            0)

        if (grid is not None and grid.value[2] > 1 and grid.value[1] > 1):
            return VirtualDesktopPager(display, screen, root)
        elif (hasattr(size, 'value')
                and (size.value[1] > screen.height_in_pixels
                     or size.value[0] > screen.width_in_pixels)):
            return ViewportPager(display, screen, root)
        else:
            # defaults to VirtualDesktop
            return VirtualDesktopPager(display, screen, root)


class Pager:

    '''Dummy pager, not intended to be used directly'''

    def __init__(self, display, screen, root):
        '''Initialization.'''

        self.display = display
        self.screen = screen
        self.root = root

    def get_desktop_tasks(self, num):
        '''Returns a list of tasks for desktop num.'''

        return self.root.get_full_property(
            self.display.get_atom('_NET_CLIENT_LIST'),
            Xatom.WINDOW).value

    def get_current_desktop(self):
        '''Returns the index of the currently active desktop.'''

        return 0

    def get_desktop_layout(self):
        '''Returns the number of rows and cols from the window manager.'''

        return (1, 1)

    def get_desktop_count(self):
        '''Returns the current number of desktops.'''

        return 1

    def get_desktop_names(self):
        '''Returns a list containing desktop names.'''

        return ['Desktop']

    def switch_desktop(self, num):
        '''Sets the active desktop to num.'''

        pass

    def send_event(self, win, ctype, data, mask=None):
        '''Sends a ClientMessage event to the root window.'''

        data = (data + [0] * (5 - len(data)))[:5]
        ev = Xlib.protocol.event.ClientMessage(
            window=win,
            client_type=ctype,
            data=(
                32,
                data))

        if not mask:
            mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
        self.root.send_event(ev, event_mask=mask)


class VirtualDesktopPager(Pager):

    '''Virtual desktop / workspace -based pager.'''
    '''Should be used with most freedesktop-compliant window managers.'''

    def get_current_desktop(self):
        '''Returns the index of the currently active desktop.'''

        return self.root.get_full_property(
            self.display.get_atom('_NET_CURRENT_DESKTOP'),
            0).value[0]

    def get_desktop_layout(self):
        '''Returns the number of rows and cols, from the window manager.'''

        grid = self.root.get_full_property(
            self.display.get_atom('_NET_DESKTOP_LAYOUT'),
            0)

        rows = 0
        cols = 0

        if grid is not None and grid.value[2] > 1 and grid.value[1] > 1:
            # if _NET_DESKTOP_LAYOUT has sane values, use them:
            rows = grid.value[2]
            cols = grid.value[1]
        else:
            # else compute nice defaults:
            count = self.get_desktop_count()
            rows = round(math.sqrt(count))
            cols = math.ceil(math.sqrt(count))

        return (int(rows), int(cols))

    def get_desktop_count(self):
        '''Returns the current number of desktops.'''

        return self.root.get_full_property(
            self.display.get_atom('_NET_NUMBER_OF_DESKTOPS'),
            0).value[0]

    def get_desktop_names(self):
        '''Returns a list containing desktop names.'''

        count = self.get_desktop_count()
        names = self.root.get_full_property(
            self.display.get_atom('_NET_DESKTOP_NAMES'),
            0)

        if hasattr(names, 'value'):
            count = self.get_desktop_count()
            names = names.value.strip('\x00').split('\x00')[:count]
        else:
            names = []
            for i in range(count):
                names.append(str(i))

        if len(names) < count:
            for i in range(len(names), count):
                names.append(str(i))

        return names

    def switch_desktop(self, num):
        '''Sets the active desktop to num.'''

        win = self.root
        ctype = self.display.get_atom('_NET_CURRENT_DESKTOP')
        data = [num]

        self.send_event(win, ctype, data)
        self.display.flush()


class ViewportPager(Pager):

    '''Viewport-based pager.'''
    '''To be used with compiz and other viewport-based window managers.'''

    def get_sreen_resolution(self):
        '''Returns the screen resolution in pixels as (width, height).'''

        return (self.screen.width_in_pixels, self.screen.height_in_pixels)

    def get_current_desktop(self):
        '''Returns the index of the currently active desktop.'''

        w, h = self.get_sreen_resolution()
        rows, cols = self.get_desktop_layout()
        vp = self.root.get_full_property(
            self.display.get_atom("_NET_DESKTOP_VIEWPORT"),
            0).value
        return round(vp[1] / h) * cols + round(vp[0] / w)

    # TODO: optimize (cache ?)
    def get_desktop_layout(self):
        '''Returns the number of rows and cols from the window manager.'''

        w, h = self.get_sreen_resolution()
        size = self.root.get_full_property(
            self.display.get_atom("_NET_DESKTOP_GEOMETRY"),
            0)

        # default values
        rows = 1
        cols = 1

        if size is not None:
            rows = round(size.value[1] / h)
            cols = round(size.value[0] / w)

        return (int(rows), int(cols))

    def get_desktop_count(self):
        '''Returns the current number of desktops.'''

        rows, cols = self.get_desktop_layout()
        return rows * cols

    def get_desktop_names(self):
        '''Returns a list containing desktop names.'''

        count = self.get_desktop_count()
        names = []
        for i in range(count):
            names.append('Workspace {0}'.format(i + 1))

        return names

    def switch_desktop(self, num):
        '''Sets the active desktop to num.'''

        w, h = self.get_sreen_resolution()
        rows, cols = self.get_desktop_layout()
        x = int(num % cols)
        y = int(round((num - x) / cols))
        data = [x * w, y * h]

        win = self.root
        ctype = self.display.get_atom("_NET_DESKTOP_VIEWPORT")

        self.send_event(win, ctype, data)
        self.display.flush()

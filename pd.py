##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Forest Darling <fdarling@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd

BITS_PER_BYTE = 8
CHANNEL_INDEX_CLK   = 0
CHANNEL_INDEX_VALID = 1
CHANNEL_INDEX_RXD1  = 2
CHANNEL_INDEX_RXD0  = 3

DIBIT_ANNOTATION_LIST_INDEX_VALUE        = 0
DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_START = 1
DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_END   = 2
DIBIT_ANNOTATION_LIST_INDEX_CRS          = 3
DIBIT_ANNOTATION_LIST_INDEX_DV           = 4

ANNOTATION_CLASS_INDEX_OCTETS = 0
ANNOTATION_CLASS_INDEX_DIBITS = 1
ANNOTATION_CLASS_INDEX_CRS    = 2
ANNOTATION_CLASS_INDEX_DV     = 3

class ChannelError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'rmii'
    name = 'RMII'
    longname = 'Reduced Media-Independent Interface'
    desc = '10/100MBit Ethernet PHY to MAC bus'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['rmii']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'clk',    'name': 'REF_CLK', 'desc': '50MHz reference clock'},
        {'id': 'valid',  'name': 'CRS_DV or TX_EN',  'desc': 'data valid and maybe carrier sense'},
        {'id': 'dibit1', 'name': 'D1',               'desc': 'data di-bit MSB'},
        {'id': 'dibit0', 'name': 'D0',               'desc': 'data di-bit LSB'},
    )
    optional_channels = (
    )
    options = (
        {'id': 'valid_bit_type', 'desc': 'CRS_DV vs. TX_EN', 'default': 'CRS_DV', 'values': ('CRS_DV', 'TX_EN')},
    )
    annotations = (
        ('octets',  'octets'),
        ('di-bits', 'bits'),
    )
    annotation_rows = (
        ('dibits', 'di-bits', (1,)),
        ('octets', 'octets',  (0,)),
    )
    binary = (
        ('dibits', 'di-bits'),
    )

    def __init__(self):
        self.reset()

    def reset_decoder_state(self):
        self.bitcount = 0
        self.octet = 0
        self.dibits = []

    def reset(self):
        # not actually sure what this is used for besides being stored...
        self.samplerate = None

        # our internal state
        self.crs = 0
        self.dv  = 0
        self.reset_decoder_state()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
       if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putdata(self):
        # di-bit annotations
        for dibit in self.dibits:
            sample_start = dibit[DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_START]
            sample_end   = dibit[DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_END]
            self.put(sample_start, sample_end, self.out_ann, [ANNOTATION_CLASS_INDEX_DIBITS, ['%d' % dibit[DIBIT_ANNOTATION_LIST_INDEX_VALUE]]])

        # octal annotations
        sample_start = self.dibits[-1][DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_START]
        sample_end   = self.dibits[ 0][DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_END]
        self.put(sample_start, sample_end, self.out_ann, [ANNOTATION_CLASS_INDEX_OCTETS, ['%02X' % self.octet]])

    def handle_dibit(self, clk, valid, dibit1, dibit0):
        # we must de-multiplex CRS_DV
        dv_updated = False

        # for TX_EN, they are tied together:
        if self.options['valid_bit_type'] == 'TX_EN':
            self.crs = valid
            self.dv  = valid
            dv_updated = True
        # check for the "CRS" portion of "CRS_DV"
        elif (self.bitcount & 0x2) == 0:
            self.crs = valid
        # check for the "DV" portion of "CRS_DV"
        else:
            # self.dv  = True
            self.dv  = valid
            dv_updated = True

        # if the data is known to be invalid, don't emit annotations
        if dv_updated and self.dv == 0:
           self.reset_decoder_state()
           return

        # if neither carrier nor valid data, nothing to do
        if not self.crs and not self.dv:
            self.reset_decoder_state()
            return

        # clock in di-bit
        dibit = ((dibit1 << 1) | dibit0)
        self.octet |= (dibit << self.bitcount)

        # initialize the endsample for this bit (will be extended later)
        sample_end = self.samplenum
        if self.bitcount > 0:
            # TODO what is this math!?
            sample_end += self.samplenum - self.dibits[0][DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_START]

        # insert the sample at the left (beginning) of the list of di-bits
        self.dibits.insert(0, [dibit, self.samplenum, sample_end])

        # extend the "end sample" for the left-most (last inserted) di-bit annotation
        if self.bitcount > 0:
            self.dibits[1][DIBIT_ANNOTATION_LIST_INDEX_SAMPLE_END] = self.samplenum

        # advance by one di-bit
        self.bitcount += 2

        # emit completed bytes
        if self.bitcount == BITS_PER_BYTE:
            # TODO delay emitting annotations until we fix their sample lengths
            self.putdata()
            self.reset_decoder_state()

    def find_clk_edge(self, clk, valid, dibit1, dibit0, first):
        # ignore sample if the clock pin hasn't changed
        if first or not self.matched[CHANNEL_INDEX_CLK]:
            return

        # TX_EN case:
        if self.options['valid_bit_type'] == 'TX_EN':
            # only sample on the falling edge
            if clk:
                return
        # CRS_DV case:
        else:
            # only sample on the rising edge
            if not clk:
                return

        # get the RMII dibit
        self.handle_dibit(clk, valid, dibit1, dibit0)

    def decode(self):
        # make sure we have all the channels before continuing
        for channel in range(len(Decoder.channels)):
            if not self.has_channel(channel):
                raise ChannelError('All RMII signal pins are required!')

        # we care about any CLK changes
        wait_cond = [{CHANNEL_INDEX_CLK: 'e'}]

        # TODO: implement this optimization properly!
        # sometimes we only care about the clock if "valid" is now high
        #wait_cond.append({CHANNEL_INDEX_VALID: 'e'})

        # get first sample regardless of the clock state
        (clk, valid, dibit1, dibit0) = self.wait({})
        self.find_clk_edge(clk, valid, dibit1, dibit0, True)

        # process subsequent samples on positive edges of the clock
        while True:
            (clk, valid, dibit1, dibit0) = self.wait(wait_cond)
            self.find_clk_edge(clk, valid, dibit1, dibit0, False)

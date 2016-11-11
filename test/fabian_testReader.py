
import os
import heppy.framework.config as cfg
import logging
logging.basicConfig(level=logging.INFO)

# input component 
# several input components can be declared,
# and added to the list of selected components

inputSample = cfg.Component(
    'test_component',
    # create the test file by running
    # python create_tree.py
    files = [os.path.abspath('example.root')],
    )

selectedComponents  = [inputSample]

# use a simple event reader based on the ROOT TChain class


from ROOT import gSystem
gSystem.Load("libdatamodelDict")
from EventStore import EventStore as Events

from heppy.analyzers.fcc.TestReader import TestReader
testreader = cfg.Analyzer(
    TestReader,
    mode = 'ee',
    gen_particles = 'GenParticle',
    log_level=logging.INFO
    )


# definition of a sequence of analyzers,
# the analyzers will process each event in this order
sequence = cfg.Sequence([testreader])

from heppy.framework.services.tfile import TFileService
output_rootfile = cfg.Service(
    TFileService,
    'myhists',
    fname='histograms.root',
    option='recreate'
)

services = [output_rootfile]

# finalization of the configuration object. 
config = cfg.Config( components = selectedComponents,
                     sequence = sequence,
                     services = services, 
                     events_class = Events )

# print config 

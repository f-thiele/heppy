''' Class to hold all the needed papas data collections
    This includes ...
    
'''

import pprint
#import copy
import collections 
import fnmatch
from heppy.papas.data.identifier import Identifier
from heppy.papas.graphtools.DAG import Node
from heppy.papas.pfalgo.distance import Distance
from heppy.papas.mergedclusterbuilder import MergedClusterBuilder


class PapasData(object):
    '''Builds the inputs to particle flow from a collection of simulated particles:
    - collects all smeared tracks and clusters
    - merges overlapping clusters 
    '''
    print_nstrip = 10 # ask colin
    
    def __init__(self, ptcs):
        '''
        arguments
                 event: must contain
                      tracks dictionary : {id1:track1, id2:track2, ...}
                      ecal dictionary : {id1:ecal1, id2:ecal2, ...}
                      hcal dictionary : {id1:hcal1, id2:hcal2, ...}
                      
                      and these must be names according to ecalsname etc
                      blocks, sim_particles and rec_particles are optional
        '''
        self.tracks = dict()
        self.gen_tracks = dict()
        self.ecal_clusters = dict()
        self.hcal_clusters = dict()
        self.gen_ecals = dict()
        self.gen_hcals = dict()
        self.smeared_ecals = dict()
        self.smeared_hcals = dict()
        self.history = dict()
        self.sim_particles = dict()
        self.gen_stable_particles = dict()
        self.history = dict()
        
        self.build(ptcs)
        self.merge_clusters()
        
    def build(self, sim_particles):
    
        if  len(sim_particles) == 0 : # deal with case where no particles are produced
            return
    
        #these are the particles before simulation        
        sim_particles = sorted( sim_particles,
                               key = lambda ptc: ptc.e(), reverse=True)     
        
        #construct dictionaries of particles, clusters etc
        #and simulataneously construct the history from the simulated particles
        
        history = self.history
        for ptc in sim_particles:
            id = ptc.uniqueid
            self.sim_particles[id] = ptc
            history[id] = Node(id)
            gen_id = ptc.gen_ptc.uniqueid
            self.gen_stable_particles[gen_id] = ptc.gen_ptc
            history[gen_id] = Node(gen_id)
            history[gen_id].add_child(history[id])
    
            if ptc.track:
                track_id = ptc.track.uniqueid
                self.gen_tracks[track_id] = ptc.track
                history[track_id] = Node(track_id)
                history[id].add_child(history[track_id])
                if ptc.track_smeared:
                    smtrack_id = ptc.track_smeared.uniqueid
                    self.tracks[smtrack_id] = ptc.track_smeared
                    history[smtrack_id] = Node(smtrack_id)
                    history[track_id].add_child(history[smtrack_id])    
            if len(ptc.clusters) > 0 :   
                for key, clust in ptc.clusters.iteritems():
                    if key=="ecal_in" :  #todo check this .or. key=="ecal_decay" :
                        self.gen_ecals[clust.uniqueid] = clust                       
                    elif key=="hcal_in" :
                        self.gen_hcals[clust.uniqueid] = clust
                    else:
                        assert false                    
                    history[clust.uniqueid] = Node(clust.uniqueid)
                    history[id].add_child(history[clust.uniqueid])  
    
                    if len(ptc.clusters_smeared) > 0 :   
                        for key1, smclust in ptc.clusters_smeared.iteritems():
                            if (key ==key1): 
                                if key=="ecal_in" :  #todo check this .or. key=="ecal_decay" :
                                    self.smeared_ecals[smclust.uniqueid]=smclust
                                elif key=="hcal_in" :
                                    self.smeared_hcals[smclust.uniqueid]=smclust 
                                history[smclust.uniqueid] = Node(smclust.uniqueid)
                                history[clust.uniqueid].add_child(history[smclust.uniqueid])
    
    
    def merge_clusters(self):
        #Now merge the simulated clusters as a separate pre-stage (prior to new reconstruction)        
        ruler = Distance()
        self.ecal_clusters = MergedClusterBuilder(self.smeared_ecals, ruler, self.history).merged
        self.hcal_clusters = MergedClusterBuilder(self.smeared_hcals, ruler, self.history).merged
        


    def get_object(self, uniqueid):
        ''' given a uniqueid return the underlying obejct
        '''
        type = Identifier.get_type(uniqueid)
        subtype = Identifier.get_subtype(uniqueid)
        if type == Identifier.PFOBJECTTYPE.TRACK:
            if uniqueid in self.tracks :
                return self.tracks[uniqueid] 
            elif uniqueid in self.gen_tracks :
                return self.gen_tracks[uniqueid] 
            else:
                assert(False)            
        elif type == Identifier.PFOBJECTTYPE.ECALCLUSTER:      
            if uniqueid in self.ecal_clusters:            
                return self.ecal_clusters[uniqueid] 
            elif uniqueid in self.smeared_ecals:            
                return self.smeared_ecals[uniqueid]             
            elif uniqueid in self.gen_ecals:            
                return self.gen_ecals[uniqueid] 
            else:
                assert(False)            
        elif type == Identifier.PFOBJECTTYPE.HCALCLUSTER:            
            if uniqueid in self.hcal_clusters:            
                return self.hcal_clusters[uniqueid] 
            elif uniqueid in self.smeared_hcals:            
                return self.smeared_hcals[uniqueid]             
            elif uniqueid in self.gen_hcals:            
                return self.gen_hcals[uniqueid] 
            else:
                assert(False)            
        elif type == Identifier.PFOBJECTTYPE.PARTICLE:
            if subtype == 'g':            
                return self.gen_stable_particles[uniqueid] 
            elif uniqueid in self.sim_particles:            
                return self.sim_particles[uniqueid]             
            elif uniqueid in self.rec_particles:            
                return self.rec_particles[uniqueid] 
            else:  
                assert false
        elif type == Identifier.PFOBJECTTYPE.BLOCK:
            return self.blocks[uniqueid]               
        else:
            assert(False)   
   
   
   
    def lines(self):
        #approach copied from event.py and results used in printing this as part of event - improvements likely to be needed
        stripped_attrs = dict()
        for name, value in {"tracks" : self.tracks ,
                            "gen tracks" :self.gen_tracks ,
                            "ecal_clusters": self.ecal_clusters ,
                            "hcal_clusters": self.hcal_clusters ,
                            "gen_ecals": self.gen_ecals ,
                            "gen_hcals": self.gen_hcals ,
                            "smeared_hcals": self.smeared_ecals ,
                            "smeared_hcals": self.smeared_hcals ,
                            #"history": self.history ,
                            "sim_particles": self.sim_particles ,
                            "gen_stable_particles": self.gen_stable_particles }.iteritems() :
            stripped_attrs[name] = value
        for name, value in stripped_attrs.iteritems():
            if hasattr(value, '__len__') and len(value)>self.__class__.print_nstrip+1:
                # taking the first 10 elements and converting to a python list 
                # note that value could be a wrapped C++ vector
                if isinstance(value, collections.Mapping):
                    entries = [entry for entry in value.iteritems()]
                    entries = entries[:self.__class__.print_nstrip]
                    entries
                    stripped_attrs[name] = dict(entries)
                else:
                    stripped_attrs[name] = [ val for val in value[:self.__class__.print_nstrip] ]
                    stripped_attrs[name].append('...')
                    stripped_attrs[name].append(value[-1])    
        return stripped_attrs
                
    def __str__(self):
        header = 'PapasData:'
        stripped_attrs = self.lines()
        contents = pprint.pformat(stripped_attrs, indent=4)
        return '\n'.join([header, contents])
        
        
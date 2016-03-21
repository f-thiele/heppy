from heppy.papas.aliceproto.identifier import Identifier
from heppy.papas.aliceproto.DAG import Node
from heppy.papas.aliceproto.blocksplitter import BlockSplitter
from heppy.papas.pdt import particle_data
from heppy.papas.path import StraightLine, Helix
from heppy.papas.pfobjects import Particle

from ROOT import TVector3, TLorentzVector
import math
import pprint

class PFReconstructor(object):
    ''' The reconstructor takes blocks of elements
        and attempts to reconstruct particles
        The following strategy is used (to be checked with Colin)
        single elements:
             track -> charged hadron
             hcal  -> neutral hadron
             ecal  -> photon
        connected elements:
             has hcal and has a track
                -> add up all connected tracks, turn each track into a charged hadron
                -> add up all ecal energies
                -> if track energies is greater than hcal energy then turn the missing energies into an ecal (photon)
                      NB this links the photon to the hcal rather than the ecals
                -> if track energies are less than hcal then make a neutral hadron with rest of hcal energy and turn all ecals into photons
              has hcal but no track (nb by design there will be no attached ecals because hcal ecal links have been removed)
                -> make a neutral hadron
              has hcals
                -> each hcal is treated using rules above
              has track(s) 
                -> each track is turned into a charged hadron
              has track(s) and  ecal(s)
                -> the tracks are turned into charged hadrons, the ecals are marked as locked but energy is not checked and no photons are made
              has only ecals 
                -> TODO/appears not to be used (has this already been removed in earlier steps?)
        
             
         If history_nodes are provided then the particles are linked into the exisiting history
         
         Contains:
            blocks: the dictionary of blovks to be reconstructed { blockid; block }
            unused: list of unused elements
            particles: list of constructed particles
            history_nodes: optional, desribes links between elements, blocks, particles
            '''    
    def __init__(self,event): # not sure about what the arguments should be here
        ''' Event should contain blocks and optionally history_nodes'''
        self.blocks=event.blocks
        self.unused = []
        self.particles = [] 
        
        # history nodes will be used to connect reconstructed particles into the history
        # its optional at the moment
        if hasattr(event, "history_nodes") :
            self.history_nodes = event.history_nodes
        else : 
            self.history_nodes = None
        
        # edit the links so that each track will end up linked to at most one hcal
        # then recalculate the blocks
        for block in self.blocks.itervalues():   
            splitblocks = self.simplified_blocks(block,event.history_nodes)
            if splitblocks!=None :
                self.blocks.update(splitblocks)
            
        #reconstruct each of the resulting blocks        
        for block in self.blocks.itervalues():  
            if block.is_active: # when blocks are split the original gets deactivated
                self.particles.extend(self.reconstruct_block(block))
                self.unused.extend( [id for id in block.element_uniqueids if not self.locked[id]])
        if len(self.unused)> 0 :
            print unused
        print(str(self))        
        
 
            
    def simplified_blocks(self, block,history_nodes=None):
        
        ''' Block: a block which contains list of element ids and set of edges that connect them
            history_nodes: optional dictionary of Nodes with element identifiers in each node
        
        returns None or a dictionary of new split blocks
            
        The goal is to remove, if needed, some links from the block so that each track links to 
        at most one hcal within a block. In some cases this may separate a block into smaller
        blocks (splitblocks). The BlockSplitter is used to return the new smaller blocks.
         If history_nodes are provided then the history will be updated. Split blocks will 
         have the tracks and cluster elements as parents, and also the original block as a parent
        '''
        
        ids=block.element_uniqueids
        
        
        if len(ids)<=1 : # no links to remove
            return  None #no split blocks
        
        # work out any links that need to be removed        
        to_unlink = []        
        for id in ids :
            if Identifier.is_track(id) :
                linked = block.linked_edges(id,"hcal_track") # NB already sorted from small to large distance
                if linked!=None :
                    first_hcal = True
                    for elem in linked:
                        if first_hcal:
                            first_hcal = False
                        else:
                            to_unlink.append(elem)
            elif Identifier.is_ecal(id) :
                # this is now handled in distance and so could be removed
                # remove all ecal-hcal links. ecal linked to hcal give rise to a photon anyway.
                linked = block.linked_edges(id,"ecal_hcal")
                to_unlink.extend(linked)
        
        #if there is something to unlink then use the BlockSplitter        
        splitblocks=None        
        if len(to_unlink) :
            splitblocks= BlockSplitter(block,to_unlink,history_nodes).blocks
        
        return splitblocks
            
    def reconstruct_block(self, block):
        ''' see class description for summary of reconstruction approach
        '''
        particles = []
        ids=block.element_uniqueids
        self.locked=dict()
        for id in ids:
            self.locked[id] = False
        
       
        if len(ids)==1: #TODO WARNING!!! LOTS OF MISSING CASES
            id = ids[0]
            
            if Identifier.is_ecal(id) :
                particles.append(self.reconstruct_cluster(block.pfevent.ecal_clusters[id],"ecal_in"))
            elif Identifier.is_hcal(id) :
                particles.append(self.reconstruct_cluster(block.pfevent.hcal_clusters[id],"hcal_in"))
            elif Identifier.is_track(id) :
                particles.append(self.reconstruct_track(block.pfevent.tracks[id])) # ask Colin about energy balance - what happened to the associated clusters that one would expect?
        else: #TODO
            for id in ids :
                if Identifier.is_hcal(id) :
                    particles.extend(self.reconstruct_hcal(block,id))
            for id in ids :
                if Identifier.is_track(id) and not self.locked[id] :
                # unused tracks, so not linked to HCAL
                # reconstructing charged hadrons.
                # ELECTRONS TO BE DEALT WITH.
                    particles.append(self.reconstruct_track(block.pfevent.tracks[id]))
                    # tracks possibly linked to ecal->locking cluster
                    for idlink in block.linked_ids(id,"ecal_track") :
                        #ask colin what happened to possible photons here:
                        self.locked[idlink] = True
                        
            # #TODO deal with ecal-ecal
            # ecals = [elem for elem in group if elem.layer=='ecal_in'
            #          and not elem.locked]
            # for ecal in ecals:
            #     linked_layers = [linked.layer for linked in ecal.linked]
            #     # assert('tracker' not in linked_layers) #TODO electrons
            #     self.log.warning( 'DEAL WITH ELECTRONS!' ) 
            #     particles.append(self.reconstruct_cluster(ecal, 'ecal_in'))
            #TODO deal with track-ecal
        return particles 
    
    def insert_particle_history(self, particle, tracks = None, clusters = None):
        
        
        if (self.history_nodes == None) :
            return
        
        if particle.uniqueid in self.history_nodes :
            pnode = self.history_nodes[particle.uniqueid]
        else :
            pnode = Node(particle.uniqueid)
            self.history_nodes[particle.uniqueid] = pnode
        if clusters != None : 
            for cluster in clusters :
                self.history_nodes[cluster.uniqueid].add_child(pnode)
        if tracks != None :
            for track in tracks :
                self.history_nodes[track.uniqueid].add_child(pnode)  
    

    def neutral_hadron_energy_resolution(self, hcal):
        '''WARNING CMS SPECIFIC! 

        http://cmslxr.fnal.gov/source/RecoParticleFlow/PFProducer/src/PFAlgo.cc#3350 
        '''
        energy = max(hcal.energy, 1.)
        stoch, const = 1.02, 0.065
        if abs(hcal.position.Eta())>1.48:
            stoch, const = 1.2, 0.028
        resol = math.sqrt(stoch**2/energy + const**2)
        return resol

    def nsigma_hcal(self, cluster):
        '''WARNING CMS SPECIFIC! 
        
        http://cmslxr.fnal.gov/source/RecoParticleFlow/PFProducer/src/PFAlgo.cc#3365 
        '''
        
        return 1. + math.exp(-cluster.energy/100.)
        
        
    def reconstruct_hcal(self, block, hcalid):
        '''
           block: element ids and edges 
           hcalid: id of the hcal being processed her
        
           has hcal and has a track
                -> add up all connected tracks, turn each track into a charged hadron
                -> add up all ecal energies
                -> if track energies is greater than hcal energy then turn the missing energies into an ecal (photon)
                      NB this links the photon to the hcal rather than the ecals
                -> if track energies are less than hcal then make a neutral hadron with rest of hcal energy and turn all ecals into photons
              has hcal but no track (nb by design there will be no attached ecals because hcal ecal links have been removed)
                -> make a neutral hadron
              has hcals
                -> each hcal is treated using rules above
        '''
        #ask Colin - tracks and ecals group together so what does this mean for history, should we$
        #try and split it up better
        # hcal used to make ecal_in has a couple of possible issues
        particles = []
        tracks = []
        ecals = []
        hcal =block.pfevent.hcal_clusters[hcalid]
        
        assert(len(block.linked_ids(hcalid, "hcal_hcal"))==0  )
               
        for trackid in block.linked_ids(hcalid, "hcal_track"):
            tracks.append(block.pfevent.tracks[trackid])
            for ecalid in block.linked_ids(trackid, "ecal_track") :
                # the ecals get all grouped together for all tracks in the block
                # Maybe we want to link ecals to their closest track etc?
                # this might help with history work
                # ask colin.
                if not self.locked[ecalid] :
                    ecals.append(block.pfevent.ecal_clusters[ecalid])
                    self.locked[ecalid]  = True
                # hcal should be the only remaining linked hcal cluster (closest one)
                #thcals = [th for th in elem.linked if th.layer=='hcal_in']
                #assert(thcals[0]==hcal)
        print( 'Reconstruct Hcal {hcal}'.format(hcal=hcal) )
        print( '\tT {tracks}'.format(tracks=tracks) )
        print( '\tE {ecals}'.format(ecals=ecals) )
        hcal_energy = hcal.energy
        if len(tracks):
            ecal_energy = sum(ecal.energy for ecal in ecals)
            track_energy = sum(track.energy for track in tracks)
            for track in tracks:
                #make a charged hadron
                particles.append(self.reconstruct_track( track))
                
            delta_e_rel = (hcal_energy + ecal_energy) / track_energy - 1.
            # WARNING
            # calo_eres = self.detector.elements['hcal'].energy_resolution(track_energy)
            calo_eres = self.neutral_hadron_energy_resolution(hcal)
            print( 'dE/p, res = {derel}, {res} '.format(
                derel = delta_e_rel,
                res = calo_eres ))
            if delta_e_rel > self.nsigma_hcal(hcal) * calo_eres: # approx means hcal energy + ecal energies > track energies
                
                excess = delta_e_rel * track_energy # energy in excess of track energies
                print( 'excess = {excess:5.2f}, ecal_E = {ecal_e:5.2f}, diff = {diff:5.2f}'.format(
                    excess=excess, ecal_e = ecal_energy, diff=excess-ecal_energy))
                if excess <= ecal_energy: # approx means hcal energy > track energies 
                    # Make a photon from the ecal energy
                    # We make only one photon using only the combined ecal energies
                    # ask Colin why we don't use individual ecals
                    # we construct using the hcal, it makes for a trickier time with setting up the history
                    # some ecals should be linked to the new particles.
                    particles.append(self.reconstruct_cluster(hcal, 'ecal_in',
                                                              excess))
                else: # approx means that hcal energy>track energies so we must have a neutral hadron
                    #excess-ecal_energy is approximately hcal energy  - track energies
                    particle = self.reconstruct_cluster(hcal, 'hcal_in',
                                                        excess-ecal_energy)
                    if particle:
                        particles.append(particle)
                    if ecal_energy:
                        #make a photon from the remaining ecal energies
                        #again history is confusingbecause hcal is used to provide direction
                        #be better to make several smaller photons one per ecal?
                        particles.append(self.reconstruct_cluster(hcal, 'ecal_in',
                                                                  ecal_energy))

        else: # case whether there are no tracks make a neutral hadron for each hcal
              # note that hcal-ecal links have been removed so hcal should only be linked to 
              # other hcals
            
            for elem in hcal.linked:
                assert(elem.layer=='hcal_in')
                
            particles.append(self.reconstruct_cluster(hcal, 'hcal_in'))
            
            
        self.locked[hcalid] = True
        return particles 
                
    def reconstruct_cluster(self, cluster, layer, energy=None, vertex=None):
        '''construct a photon if it is an ecal
           construct a neutral hadron if it is an hcal
        '''        
        if vertex is None:
            vertex = TVector3()
        pdg_id = None
        if layer=='ecal_in':
            pdg_id = 22 #photon
        elif layer=='hcal_in':
            pdg_id = 130 #K0
        else:
            raise ValueError('layer must be equal to ecal_in or hcal_in')
        assert(pdg_id)
        mass, charge = particle_data[pdg_id]
        if energy is None:
            energy = cluster.energy
        if energy < mass: 
            return None 
        momentum = math.sqrt(energy**2 - mass**2)
        p3 = cluster.position.Unit() * momentum
        p4 = TLorentzVector(p3.Px(), p3.Py(), p3.Pz(), energy)
        particle = Particle(p4, vertex, charge, pdg_id)
        
        #ask Colin - nb I know this history is wrong as the particle really comes from ecals - how do we assign to ecals
        #TODO DISCUSS        
        self.insert_particle_history(particle,None,[cluster])
        path = StraightLine(p4, vertex)
        path.points[layer] = cluster.position #alice: this may be a bit strange because we can make a photon with a path where the point is actually that of the hcal?
                                            # nb this only is problem if the cluster and the assigned layer are different
        particle.set_path(path)
        particle.clusters[layer] = cluster  # not sure about this either when hcal is used to make an ecal cluster?
        self.locked[cluster.uniqueid] = True #just OK but not nice if hcal used to make ecal.
        return particle
        
    def reconstruct_track(self, track, clusters=None): # cluster argument does not ever seem to be used at present
        '''construct a charged hadron from the track
        '''
        vertex = track.path.points['vertex']
        pdg_id = 211 * track.charge
        mass, charge = particle_data[pdg_id]
        p4 = TLorentzVector()
        p4.SetVectM(track.p3, mass)
        particle = Particle(p4, vertex, charge, pdg_id)
        particle.set_path(track.path)
        particle.clusters = clusters
        self.insert_particle_history(particle,[track],clusters)
        self.locked[track.uniqueid] = True
        return particle


    def __str__(self):
        theStr = ['Particles:']
        theStr.extend( map(str, self.particles))
        theStr.append('Unused:')
        if len(self.unused)==0:
            theStr.append('None')
        else:
            theStr.extend( map(str, self.unused))
        return '\n'.join( theStr )

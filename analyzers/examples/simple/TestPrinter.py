from heppy.framework.analyzer import Analyzer
import pdb

class TestPrinter(Analyzer):

    def beginLoop(self, setup):
        super(TestPrinter, self).beginLoop(setup)
        self.branch = self.cfg_ana.branch
        self.leaf = self.cfg_ana.leaf

    def process(self, event):
        #pdb.set_trace()
        if(self.leaf != None):
            t = event.input.GetLeaf(self.branch, self.leaf)
            for i in range(t.GetLen()):
                self.logger.info(
                    "event {iEv}, {leafname} {var1}".format(
                        iEv = event.iEv, var1 = t.GetValue(i), leafname=self.leaf
                    ))

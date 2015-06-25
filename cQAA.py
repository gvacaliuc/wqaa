import numpy
import numpy as np
import math
import scipy.stats
import matplotlib.pyplot as plt
from KabschAlign import *
from IterativeMeansAlign import *
from MDAnalysis.core.Timeseries import *
from MDAnalysis import *
from numpy import *
from jade import *
import timing

#a is mem-mapped array, b is array in RAM we are adding to a. Not used currently in cQAA 
def mmap_concat(a,b):
	assert(a.shape[0] == b.shape[0]);
	c = np.memmap('dihedral_data.array', dtype='float64', mode='r+', shape=(a.shape[0],a.shape[1]+b.shape[1]), order='F')
	c[:, a.shape[1]: ] = b
	return c

#	Main Code
def qaa(config, val):
	iterAlign = IterativeMeansAlign();
	itr = []; avgCoords = []; eRMSD = []; newCoords = [];
	start_traj = config['startTraj'];
	num_traj = config['numOfTraj'];
	for i in range(start_traj,num_traj):
		u = MDAnalysis.Universe("traj-format_kbh/1KBH%i_ww.pdb" %(i+1), "traj-format_kbh/1KBH_%i_50k.dcd" %(i+1), permissive=False);
		atom = u.selectAtoms('name CA');

		if val.verbose: timing.log('Processing Trajectory %i...' %(i+1))

		cacoords = []; frames = [];
		print atom.numberOfResidues();
		for ts in u.trajectory:
			f = atom.coordinates();
			cacoords.append(f.T);
			frames.append(ts.frame);
		
		print array(cacoords).shape

		[a, b, c, d] = iterAlign.iterativeMeans(array(cacoords), 0.150, 4);
		itr.append(a);
		avgCoords.append(b[-1]);
		eRMSD.append(c);
		newCoords.append(d);
	
	print array(newCoords).shape

	#	Final averaging
	[itr, avgCoords, eRMSD, newCoords] = iterAlign.iterativeMeans(array(newCoords).reshape(-1,3,newCoords[0].shape[2]), 0.001, 4);
	
	if val.debug: print 'eRMSD shape: ', numpy.shape(eRMSD);
	if val.debug: print 'newC shape: ', newCoords.shape;
	if val.debug: print 'len: ', len(newCoords)
	
	#	Reshaping of coords
	coords = numpy.reshape(newCoords, (len(newCoords), -1)).T;
	
	if val.debug: print 'coords: ', numpy.shape(coords); 
	
	avgCoords = numpy.mean(coords, 1); 
	if val.debug: print avgCoords;
	
	if val.debug: print 'avgCoords: ', numpy.shape(avgCoords);
	
	if val.graph:
		tmp = numpy.reshape(numpy.tile(avgCoords, num_coords), (num_coords,-1)).T;
		caDevsMD = coords - tmp;
		#print numpy.shape(caDevsMD); print caDevsMD[0];
		D = caDevsMD.flatten(); print numpy.shape(D);
		gm = numpy.mean(D); 
		gs = numpy.std(D);
		gK = scipy.stats.kurtosis(D,0,fisher=False);
		
		[n,s] = numpy.histogram(D, bins=51,normed=1);
		
		gp = numpy.exp(-(s-gm)**2/(2*gs*gs));
		gp = gp/numpy.sum(gp); print numpy.shape(gp);
		
		lo = 0; hi = len(s);
		
		fig = plt.figure();
		ax = fig.add_subplot(111);
		x = 0.5*(s[1:] + s[:-1]);
		#ax.semilogy(s[lo:hi], gp[lo:hi],'c-',linewidth=2);
		ax.hold(True); 
		ax.semilogy(x, n, 'k-', linewidth=2.0); ax.axis('tight');
		print 'fig1'
		plt.show();
	
	
		#print 'Mean: ', gm;
		print 'Std. dev: ', gs;
		print 'Kurtosis: ', gK;
		
		cc = coords[:,0]; print numpy.shape(cc);
		cc = numpy.reshape(cc, (dim,Na));
		#print numpy.shape(coords[0:-1:3,0]), numpy.shape(coords[1:-1:3,0]), numpy.shape(coords[2:-1:3,0]);
		
		fig = plt.figure();
		ax = fig.add_subplot(111, projection='3d');
		ax.plot(cc[0,:], cc[1,:], cc[2,:]);
		print 'fig2'
		plt.show();
		
		print numpy.shape(numpy.cov(coords));
		numpy.save('cov_ca.npy', numpy.cov(coords));
		[pcas,pcab] = numpy.linalg.eigh(numpy.cov(coords));
		#numpy.save('pcab_ca.npy', pcab);
		print pcas.shape, pcab.shape
		print 'pcas: ', pcas
		si = numpy.argsort(-pcas.ravel()); print si;
		pcaTmp = pcas;
		pcas = numpy.diag(pcas);
		pcab = pcab[:,si];
	
		#fig = plt.figure();
		#ax = fig.add_subplot(111);
		#cs = ax.contourf(numpy.cov(coords));
		##ax.colorbar(cs); 
		#plt.show();
		
		fig = plt.figure();
		ax = fig.add_subplot(111);
		y = numpy.cumsum(pcaTmp.ravel()/numpy.sum(pcaTmp.ravel()));
		ax.plot(y);
		print 'fig3';
		plt.show();
		
		fig = plt.figure();
		ax = fig.add_subplot(111, projection='3d');
		pcacoffs = numpy.dot(pcab.conj().T, caDevsMD);
		print numpy.shape(pcacoffs);
		ax.scatter(pcacoffs[0,:], pcacoffs[1,:], pcacoffs[2,:], marker='o', c=[0.6,0.6,0.6]);
		print 'fig4';
		plt.show();
		
		
	# some set up for running JADE
	subspace = config['icadim'];
	lastEig = subspace; # number of eigen-modes to be considered
	numOfIC = subspace; # number of independent components to be resolved
	
	if val.graph:
		plt.plot(range(trajlen),rad_gyr[:], 'r--', lw=2)
		plt.show()
	
	icajade = jadeR(coords, lastEig);
	if (val.save) and __name__ == '__main__': np.save('icajade%s_%i.npy' %(config['pname'], config['icadim']), icajade) 

	if val.debug: print 'icajade: ', numpy.shape(icajade);
	icacoffs = icajade.dot(fulldat)
	icacoffs = numpy.asarray(icacoffs);
	if val.debug: print 'icacoffs: ', numpy.shape(icacoffs);

	if (val.save) and __name__ == '__main__': np.save('icacoffs%s_%i.npy' %(config['pname'], config['icadim']), icacoffs) 
	
	if val.graph:	
		fig = plt.figure();
		ax = fig.add_subplot(111, projection='3d');
		ax.scatter(icacoffs[0,:], icacoffs[1,:], icacoffs[2,:], marker='o', c=[0.6,0.6,0.6]); 
		print 'First 3 Dimensions of Icacoffs';
		plt.show();

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-g', action='store_true', dest='graph', default=False, help='Shows graphs.')
	parser.add_argument('-v', action='store_true', dest='verbose', default=False, help='Runs program verbosely.')
	parser.add_argument('-s', '--save', action='store_true', dest='save', default=False, help='Saves important matrices.')
	parser.add_argument('-d', '--debug', action='store_true', dest='debug', default=False, help='Prints debugging help.')

	values = parser.parse_args()
	if values.debug: values.verbose = True;

#	Config settings -- only here if cQAA is called directly from python
	config = {};
	config['numOfTraj'] = 1;
	config['icadim'] = 40;
	config['pname'] = 'PROTEIN';	#	Edit to fit your protein name
	qaa(config, values);
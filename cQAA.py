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
import argparse
from scipy.stats import kurtosis
import os.path as path

#a is mem-mapped array, b is array in RAM we are adding to a.
def mmap_concat(shape,b,filename):
	assert(shape[1] == b.shape[1] and shape[2] == b.shape[2]);
	c = np.memmap(filename, dtype='float64', mode='r+', shape=(shape[0]+b.shape[0],shape[1],shape[2]))
	c[shape[0]:, :, : ] = b
	newshape = c.shape;	
	del c;	#	Flushes changes to memory and then deletes.  New array can just be called using filename
	return newshape;

#	Main  Code
#	||		||
#	\/		\/

#================================================
def qaa(config, val):

	iterAlign = IterativeMeansAlign();
	itr = []; avgCoords = []; eRMSD = [];
	start_traj = config['startTraj'];
	num_traj = config['numOfTraj'];
	startRes = config['startRes'];
	numRes = config['numRes'];
	slice_val = config['slice_val'];
	fulldat = [];
	dim = 3;
	global dt;

	#	BEGIN FOR LOOP -------------------------------
	for i in range(start_traj,start_traj+num_traj):

		#	Import from MDAnalysis			
		#	!Edit to your trajectory format!
		try:
			u = MDAnalysis.Universe("ubq/protein.pdb", "ubq/pnas2013-native-1-protein-%03i.dcd" %(i), permissive=False);
		except:
			raise ImportError('You must edit \'cQAA.py\' to fit your trajectory format!');
			exit();

		atom = u.selectAtoms('name CA');
		resname = atom.resnames();
		dt = u.trajectory.dt;

		if val.debug: print 'dt: ', dt;
		if val.verbose: timing.log('Processing Trajectory %i...' %(i+1))

		counter = 0;	#	For slicing trajectory
		cacoords = []; frames = [];

		for ts in u.trajectory:
			if (counter % config['slice_val'] == 0):
				f = atom.coordinates();
				cacoords.append(f.T);
				frames.append(ts.frame);
			counter = counter + 1;

		#	Alignment
		if numRes == -1:
			numRes = atom.numberOfResidues();
		if atom.numberOfResidues() == numRes:
			[a, b, c, d] = iterAlign.iterativeMeans(array(cacoords)[:,:,:], 0.150, 4, val.verbose);
		else:
			[a, b, c, d] = iterAlign.iterativeMeans(array(cacoords)[:,:,startRes:startRes+numRes], 0.150, 4, val.verbose);

		#	Storing Data	
		itr.append(a);
		avgCoords.append(b[-1]);
		eRMSD.append(c);
		fulldat.append(d);
	
	#	END FOR LOOP ------------------------------

	if val.debug: print len(fulldat);
	if val.debug: print numRes, dim;

	#	Converts fulldat from list to ndarray	
	try:
		fulldat = np.array(fulldat).reshape( (-1, dim, numRes) )
	except:
		tmp = [];
		for i in fulldat:
			for j in i:
				tmp.append(j);
		fulldat = np.array(tmp);

	print fulldat.shape;	
	num_coords = fulldat.shape[0];
	dim = fulldat.shape[1];
	num_atoms = fulldat.shape[2];
	trajlen = len(u.trajectory) / slice_val

	if val.debug and val.save: np.save('savefiles/%s_full_prealign.npy' %(config['pname']), np.array(fulldat));
	if val.debug: print 'num_coords: ', num_coords;
	
	#	Final alignment	--------------
	if num_traj > 1:
		[itr, avgCoords, eRMSD, fulldat ] = iterAlign.iterativeMeans(fulldat, 0.150, 4, val.verbose);	

	if val.debug: print 'eRMSD shape: ', numpy.shape(eRMSD);
	if val.save: np.save('savefiles/%s_eRMSD.npy' %(config['pname']), eRMSD );
	if val.debug and val.save: np.save('savefiles/%s_full_postalign.npy' %(config['pname']), np.array(fulldat));

	#	Reshaping of coords	--------------
	coords = fulldat.reshape((fulldat.shape[0],-1), order='F').T

	if val.save: np.save('savefiles/%s_coords.npy' %(config['pname']), coords)
	pdbgen(fulldat, resname, config, val);
	jade_calc(config, coords, val, avgCoords, num_coords);

#================================================
def minqaa(config, val, fulldat):
	#	Setup
	iterAlign = IterativeMeansAlign();
	itr = []; avgCoords = []; eRMSD = [];
	dim = 3;
	assert(len(fulldat.shape) == 3);
	num_coords = fulldat.shape[0];
	dim = fulldat.shape[1];
	num_atoms = fulldat.shape[2];
	
	#	Final averaging
	[itr, avgCoords, eRMSD, fulldat ] = iterAlign.iterativeMeans(fulldat, 0.150, 4, val.verbose);	
	
	if val.debug: print 'eRMSD shape: ', numpy.shape(eRMSD);
	if val.save: np.save('savefiles/%s_eRMSD.npy' %(config['pname']), eRMSD );
	
	#	Reshaping of coords
	coords = fulldat.reshape((fulldat.shape[0],-1), order='F').T

	if val.save: np.save('savefiles/%s_coords.npy' %(config['pname']), coords)
	#pdbgen(fulldat, resname);
	jade_calc(config, coords, val, avgCoords, num_coords);

#================================================
def jade_calc(config, coords, val, avgCoords, num_coords):

	dim = 3;
	numres = coords.shape[0]/dim;
	#	Stats to determine % of time exhibiting anharmonicity
	anharm = np.zeros((3,numres));
	for i in range(3):
		for j in range(numres):
			tmp = ((coords[i::3,:])[j])
			median = np.median(tmp);
			stddev = np.std(tmp);
			anharm[i,j] = float( np.sum( (np.abs(tmp - median) > 2*stddev) ) ) / num_coords;
	if val.save: np.save('savefiles/coord_anharm_%s.npy' %(config['pname']), anharm );
	
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
		if val.verbose: print 'Std. dev: ', gs;
		if val.verbose: print 'Kurtosis: ', gK;
		
		cc = coords[:,0]; print numpy.shape(cc);
		#print numpy.shape(coords[0:-1:3,0]), numpy.shape(coords[1:-1:3,0]), numpy.shape(coords[2:-1:3,0]);
		
		fig = plt.figure();
		ax = fig.add_subplot(111, projection='3d');
		ax.plot(cc[::dim], cc[1::dim], cc[2::dim]);
		print 'fig2'
		plt.show();
		
		if val.debug: print numpy.shape(numpy.cov(coords));
		numpy.save('cov_ca.npy', numpy.cov(coords));
		[pcas,pcab] = numpy.linalg.eigh(numpy.cov(coords));
		#numpy.save('pcab_ca.npy', pcab);
		if val.debug: print pcas.shape, pcab.shape
		if val.verbose: print 'pcas: ', pcas
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
		ax = fig.add_subplot(111, projection='3d');
		pcacoffs = numpy.dot(pcab.conj().T, caDevsMD);
		if val.debug: print numpy.shape(pcacoffs);
		ax.scatter(pcacoffs[0,:], pcacoffs[1,:], pcacoffs[2,:], marker='o', c=[0.6,0.6,0.6]);
		print 'fig4';
		plt.show();

	#==========================================================================	
	#	Setup to determine proper ICA dimensionality
	if val.setup:
		[pcas,pcab] = numpy.linalg.eig(numpy.cov(coords));
		si = numpy.argsort(-pcas.ravel());
		pcaTmp = pcas;
		pcas = numpy.diag(pcas);
		pcab = pcab[:,si];
		
		fig = plt.figure();
		ax = fig.add_subplot(111);
		y = numpy.cumsum(pcaTmp.ravel()/numpy.sum(pcaTmp.ravel()));
		ax.plot(y*100);
		ax.set_xlabel('Number of Principal Components');
		ax.set_ylabel('Percent of Total Variance Preserved');
		ax.set_title('Variance of Principal Components');
		if val.verbose: print('Cov. Matrix spectrum cum. sum.');
		plt.show();
		a = input('Enter desired ICA dimension (enter -1 for default): ');
		if (a > 0):
			config['icadim'] = a;
	#	End ICA Setup
	#==========================================================================
	
	#==========================================================================	
	#	Kurtosis Sliding Window Computation

	if val.verbose: timing.log('Computing kurtosis...');
	#	coords = 3*numRes x numSamples
	window = config['kurtosis_window'];
	kurt = [];
	#dt = u.trajectory.dt; #	Time Delta btwn. frames
	h = (1/2.)*dt*window #	Half-Life of window (in nanoseconds), should be: dt*(window_len)/2??
	tao = (h/dt)/np.log(2);
	weights = np.arange(window);
	#alpha = 1 - np.exp(tao**-1);	#	From paper
	alpha = (1 - np.exp(tao**-1)) / (np.exp((-window - 1)*tao**-1) - 1);	#	reciprocal of summation of W(k)
	W = lambda k: alpha*np.exp(-(window-k)*tao**-1);
	weights = map(W, weights);
	
	if val.debug: print np.sum(weights);

	for i in range(window, coords.shape[1]):
		kurt.append(np.mean(kurtosis(coords[:,i-window:i].dot(np.diag(weights)), axis=1)));
	
	if val.save: np.save('savefiles/%s_kurtosis.npy' %(config['pname']), np.array(kurt));
	if val.verbose: timing.log('Kurtosis computed -- moving to JADE...');

	#	End Kurtosis
	#========================================================================== IN PROGRESS
	
	if val.debug and val.save:
		np.save('coords_%s.npy' %(config['pname']) , coords);	

	# some set up for running JADE
	subspace = config['icadim'];
	lastEig = subspace; # number of eigen-modes to be considered
	numOfIC = subspace; # number of independent components to be resolved
	
	#	Performs jade and saves if main

	print 'val.smart: ', val.smart;
	icajade = jadeR(coords, lastEig, val.smart, val.single);
	if (val.save) and __name__ == '__main__': np.save('savefiles/icajade_%s_%i.npy' %(config['pname'], config['icadim']), icajade) 

	if val.debug: print 'icajade: ', numpy.shape(icajade);

	#	Performs change of basis
	icacoffs = icajade.dot(coords)
	icacoffs = numpy.asarray(icacoffs);
	if val.debug: print 'icacoffs: ', numpy.shape(icacoffs);
	if (val.save) and __name__ == '__main__': np.save('savefiles/icacoffs_%s_%i.npy' %(config['pname'], config['icadim']), icacoffs) 
	
	if val.graph:	
		fig = plt.figure();
		ax = fig.add_subplot(111, projection='3d');
		ax.scatter(icacoffs[0,:], icacoffs[1,:], icacoffs[2,:], marker='o', c=[0.6,0.6,0.6]); 
		print 'First 3 Dimensions of Icacoffs';
		plt.show();

	#	Saves array's to a dict and returns
	icamat = {};
	icamat['icajade'] = icajade;
	icamat['icacoffs'] = icacoffs;
	return icamat;

#================================================

def pdbgen(fulldat, resname, config, val):
	
	if val.verbose: print 'Constructing PDB file...';
	f = open('savefiles/%s.pdb' %(config['pname']), 'w+');
	for i in range(fulldat.shape[0]):
		f.write('%-6s    %4i\n' %('MODEL', i+1));
		for j in range(fulldat.shape[2]):
			f.write('%-6s%5i  CA  %s  %4i    %8.3f%8.3f%8.3f%6.2f%6.2f           C  \n' \
				%('ATOM', j+1, resname[j], j+1, fulldat[i,0,j], fulldat[i,1,j], fulldat[i,2,j], 0.0, 0.0));
		f.write('ENDMDL\n');
	f.close();
	if val.verbose: print 'PDB file completed!';

#================================================

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-g', action='store_true', dest='graph', default=False, help='Shows graphs.')
	parser.add_argument('-v', action='store_true', dest='verbose', default=False, help='Runs program verbosely.')
	parser.add_argument('-s', '--save', action='store_true', dest='save', default=False, help='Saves important matrices.')
	parser.add_argument('-d', '--debug', action='store_true', dest='debug', default=False, help='Prints debugging help.')
	parser.add_argument('--setup', action='store_true', dest='setup', default=False, help='Runs setup calculations: Cum. Sum. of cov. spectrum\nand unit radius neighbor search.')
	parser.add_argument('-i', '--input', type=str, dest='coord_in', default='null', help='Allows direct inclusion of an array of coordinates. Input as [numRes, 3, numSamp].')
	parser.add_argument('--single', action='store_true', dest='single', default=False, help='Runs jade w/ single precision. NOT recommended.')
	parser.add_argument('--smart', action='store_true', dest='smart', default=False, help='Runs jade using an alternative diagonalization setup. Refer to Cardoso\'s code for more details.')

	values = parser.parse_args()
	if values.debug: values.verbose = True;

#	Config settings -- only here if cQAA is called directly from python
	config = {};
	config['numOfTraj'] = 10;
	config['startTraj'] = 0;
	config['icadim'] = 60;
	config['pname'] = 'kurt_test_ubq';	#	Edit to fit your protein name
	config['startRes'] = 0;

	config['numRes']=-1;
	config['slice_val'] = 10;
	config['kurtosis_window'] = 100;
	if (values.coord_in == 'null'):
		qaa(config, values);
	else:
		minqaa(config, values, np.load(values.coord_in)); 


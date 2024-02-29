import bct
import numpy as np
from tqdm import tqdm
from sklearn.utils import check_random_state
from utils import cpl_func

def strength_preserving_rand_sa_trajectory(A, rewiring_iter = 10,
                                           nstage = 100, niter = 10000,
                                           temp = 1000, frac = 0.5,
                                           connected = None, verbose = False, 
                                           seed = None):

    """
    Degree- and strength-preserving randomization of
    undirected, weighted adjacency matrix A
    while tracking energy, and global network features
    
    Parameters
    ----------
    A : (N, N) array-like
        Undirected weighted adjacency matrix
    rewiring_iter : int, optional
        Rewiring parameter. Default = 10.
        Each edge is rewired approximately rewiring_iter times.
    nstage : int, optional
        Number of annealing stages. Default = 100.
    niter : int, optional
        Number of iterations per stage. Default = 10000.
    temp : float, optional
        Initial temperature. Default = 1000.
    frac : float, optional
        Fractional decrease in temperature per stage. Default = 0.5.
    connected: bool, optional
        Whether to ensure connectedness of the randomized network.
        By default, this is inferred from data.
    verbose: bool, optional
        Whether to print status to screen at the end of every stage. 
        Default = False.
    seed: float, optional
        Random seed. Default = None.

    Returns
    -------
    B : (N, N) array-like
        Randomized adjacency matrix
    min_energy : float
        Minimum energy obtained by annealing

    Notes
    -------
    Uses Maslov & Sneppen rewiring model to produce a
    surrogate adjacency matrix, B, with the same 
    size, density, and degree sequence as A. 
    The weights are then permuted to optimize the
    match between the strength sequences of A and B 
    using simulated annealing.
    
    This function is adapted from a function written in MATLAB 
    by Richard Betzel.

    References
    -------
    Misic, B. et al. (2015) Cooperative and Competitive Spreading Dynamics
    on the Human Connectome. Neuron.
    """

    try:
        A = np.asarray(A)
    except TypeError as err:
        msg = ('A must be array_like. Received: {}.'.format(type(A)))
        raise TypeError(msg) from err
    
    if frac > 1 or frac <= 0:
        msg = ('frac must be between 0 and 1. '
               'Received: {}.'.format(frac))
        raise ValueError(msg)

    rs = check_random_state(seed)

    n = A.shape[0]
    s = np.sum(A, axis = 1) #strengths of A

    if connected is None:
        connected = False if bct.number_of_components(A) > 1 else True

    #Maslov & Sneppen rewiring
    if connected:
        B = bct.randmio_und_connected(A, rewiring_iter, seed = seed)[0]
    else:
        B = bct.randmio_und(A, rewiring_iter, seed = seed)[0]

    u, v = np.triu(B, k = 1).nonzero() #upper triangle indices
    wts = np.triu(B, k = 1)[(u, v)] #upper triangle values
    m = len(wts)
    sb = np.sum(B, axis = 1) #strengths of B

    energy = np.mean((s - sb)**2)

    energymin = energy
    wtsmin = wts.copy()

    if verbose:
        print('\ninitial energy {:.5f}'.format(energy))

    #tracking energy, and global network features
    #at each stage
    strengths_trajectory = []
    energy_trajectory = []
    cpl_trajectory = []
    clustering_trajectory = []

    for istage in tqdm(range(nstage), desc='annealing progress'):
        naccept = 0
        for (e1, e2), prob in zip(rs.randint(m, size=(niter, 2)),
                                  rs.rand(niter)
                                  ):

            #permutation
            a, b, c, d = u[e1], v[e1], u[e2], v[e2]
            wts_change = wts[e1] - wts[e2]
            delta_energy = (2 * wts_change *
                            (2 * wts_change +
                             (s[a] - sb[a]) +
                             (s[b] - sb[b]) -
                             (s[c] - sb[c]) -
                             (s[d] - sb[d])
                             )
                            )

            #permutation acceptance criterion
            if (delta_energy < 0 or prob < np.e**(-(delta_energy)/temp)):

                sb[[a, b]] -= wts_change
                sb[[c, d]] += wts_change
                wts[[e1, e2]] = wts[[e2, e1]]

                energy = np.mean((sb - s)**2)

                if energy < energymin:
                    energymin = energy
                    wtsmin = wts.copy()
                naccept = naccept + 1

        #temperature update
        temp = temp*frac
        if verbose:
            print('\nstage {:d}, temp {:.5f}, best energy {:.5f}, '
                  'frac of accepted moves {:.3f}'.format(istage, temp,
                                                         energymin,
                                                         naccept/niter))
        
        curr_B = np.zeros((n, n))
        curr_B[(u, v)] = wtsmin
        curr_B = curr_B + curr_B.T
        cpl = cpl_func(curr_B)
        #weight conversion between 0 and 1 to compute clustering coefficient
        conv_B = bct.weight_conversion(curr_B, 'normalize')
        clustering = bct.clustering_coef_wu(conv_B)
        mean_clustering = np.mean(clustering)

        strengths_trajectory.append(np.sum(curr_B, axis = 1))
        energy_trajectory.append(energymin)
        cpl_trajectory.append(cpl)
        clustering_trajectory.append(mean_clustering)

    return [strengths_trajectory, energy_trajectory, 
            cpl_trajectory, clustering_trajectory]

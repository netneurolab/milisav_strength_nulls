import bct
import numpy as np
from tqdm import tqdm
from sklearn.utils import check_random_state

def strength_preserving_rand_sa_signed(A, rewiring_iter = 10,
                                       nstage = 100, niter = 10000,
                                       temp = 1000, frac = 0.5,
                                       energy_type = 'sse', energy_func = None,
                                       R = None, verbose = False,
                                       seed = None):
    """
    Degree- and strength-preserving randomization of
    undirected, weighted, signed adjacency matrix A

    Parameters
    ----------
    A : (N, N) array-like
        Undirected weighted signed adjacency matrix
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
    energy_type: str, optional
        Energy function to minimize. Can be either:
            'sse': Sum of squares between strength sequence vectors
                   of the original network and the randomized network
            'max': The single largest value
                   by which the strength sequences deviate
            'mae': Mean absolute error
            'mse': Mean squared error
            'rmse': Root mean squared error
        Default = 'sse'.
    energy_func: callable, optional
        Callable with two positional arguments corresponding to
        two strength sequence numpy arrays that returns an energy value.
        Overwrites “energy_type”.
        See “energy_type” for specifying a predefined energy type instead.
    R : (N, N) array-like, optional
        Pre-randomized adjacency matrix.
        If None, a rewired adjacency matrix is generated using the
        Maslov & Sneppen algorithm.
        Default = None.
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
    energymin : dictionary
        Minimum energy obtained by annealing for
        the positive and negative strength sequences,
        separately.

    Notes
    -------
    Uses Maslov & Sneppen rewiring model to produce a
    surrogate adjacency matrix, B, with the same
    size, density, and degree sequence as A.
    The weights are then permuted to optimize the
    match between the strength sequences of A and B
    using simulated annealing. Positive and negative weights
    and strength sequences are treated separately.

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

    pos_A = A.copy()
    pos_A[pos_A < 0] = 0
    neg_A = A.copy()
    neg_A[neg_A > 0] = 0
    pos_s = np.sum(pos_A, axis = 1) #positive strengths of A
    neg_s = np.sum(neg_A, axis = 1) #negative strengths of A
    strengths = {'pos': pos_s, 'neg': neg_s}

    #Maslov & Sneppen rewiring
    if R is None:
        B = bct.randmio_und_signed(A, rewiring_iter, seed=seed)[0]
    else:
        B = R.copy()

    pos_B = B.copy()
    pos_B[pos_B < 0] = 0
    neg_B = B.copy()
    neg_B[neg_B > 0] = 0
    signed_B = {'pos': pos_B, 'neg': neg_B}

    B = np.zeros((n, n))
    energymin_dict = {}
    init_temp = temp
    #iteratively permuting positive and negative weights
    #to match the respective strength sequences
    for sign in ['pos', 'neg']:

        temp = init_temp

        curr_B = signed_B[sign]
        s = strengths[sign]

        u, v = np.triu(curr_B, k = 1).nonzero() #upper triangle indices
        wts = np.triu(curr_B, k = 1)[(u, v)] #upper triangle values
        m = len(wts)
        sb = np.sum(curr_B, axis = 1) #strengths of B

        if energy_func is not None:
            energy = energy_func(s, sb)
        elif energy_type == 'sse':
            energy = np.sum((s - sb)**2)
        elif energy_type == 'max':
            energy = np.max(np.abs(s - sb))
        elif energy_type == 'mae':
            energy = np.mean(np.abs(s - sb))
        elif energy_type == 'mse':
            energy = np.mean((s - sb)**2)
        elif energy_type == 'rmse':
            energy = np.sqrt(np.mean((s - sb)**2))
        else:
            msg = ("energy_type must be one of 'sse', 'max', "
                "'mae', 'mse', or 'rmse'. Received: {}.".format(energy_type))
            raise ValueError(msg)

        energymin = energy
        wtsmin = wts.copy()

        if verbose:
            print('\ninitial energy {:.5f}'.format(energy))

        for istage in tqdm(range(nstage), desc = 'annealing progress'):

            naccept = 0
            for i in range(niter):

                #permutation
                e1 = rs.randint(m)
                e2 = rs.randint(m)

                a, b = u[e1], v[e1]
                c, d = u[e2], v[e2]

                sb_prime = sb.copy()
                sb_prime[[a, b]] = sb_prime[[a, b]] - wts[e1] + wts[e2]
                sb_prime[[c, d]] = sb_prime[[c, d]] + wts[e1] - wts[e2]

                if energy_func is not None:
                    energy_prime = energy_func(sb_prime, s)
                elif energy_type == 'sse':
                    energy_prime = np.sum((sb_prime - s)**2)
                elif energy_type == 'max':
                    energy_prime = np.max(np.abs(sb_prime - s))
                elif energy_type == 'mae':
                    energy_prime = np.mean(np.abs(sb_prime - s))
                elif energy_type == 'mse':
                    energy_prime = np.mean((sb_prime - s)**2)
                elif energy_type == 'rmse':
                    energy_prime = np.sqrt(np.mean((sb_prime - s)**2))
                else:
                    msg = ("energy_type must be one of 'sse', 'max', "
                        "'mae', 'mse', or 'rmse'. "
                        "Received: {}.".format(energy_type))
                    raise ValueError(msg)

                #permutation acceptance criterion
                if (energy_prime < energy or
                    rs.rand() < np.exp(-(energy_prime - energy)/temp)):
                    sb = sb_prime.copy()
                    wts[[e1, e2]] = wts[[e2, e1]]
                    energy = energy_prime
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

        B[(u, v)] = wtsmin
        energymin_dict[sign] = energymin
    B = B + B.T

    return B, energymin
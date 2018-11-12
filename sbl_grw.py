# Gaussian Random Walk Model

import os
import time
import argparse
import numpy as np
from scipy.stats import binom, norm
from sklearn.metrics import mutual_info_score

from hhmm_seq_gen import hhmm

results_dir = os.getcwd() + "/results/"


class SBL_GRW():

    def __init__(self, seq, sigma, s_min, s_max, s_res):
        # Initialize SBL-learned sequence and exponential forgetting parameter
        self.sequence = seq[:, 1]       # 'observation' sequence from hhmm
        self.hidden = seq[:, 0]
        self.T = len(seq)

        self.no_obs = 2

        # Define discretized space of latent variable for numerical integration
        self.sigma = sigma
        self.s_res = s_res
        self.s_space = np.linspace(s_min,s_max,s_res)

        # AP: Generate T-dim vector indicating no-alternation from t-1 to t
        self.repetition = np.zeros(self.T)
        for t in range(1, self.T):
            if self.sequence[t] == self.sequence[t - 1]:
                self.repetition[t] = 1
        self.repetition = self.repetition.astype(int)

        self.posterior = np.repeat(1./self.s_res, s_res)
        self.posterior_naive = np.zeros(s_res)

        self.P = np.zeros([self.no_obs, self.s_res, self.s_res, self.T])
        self.P_naive = np.zeros([self.no_obs, self.s_res, self.s_res])

    def update_posterior(self, t, type):
        i_ax = np.repeat(np.linspace(-5, 5, 70), 70)#-5, -5,..., -5, -4.8, -4.8,....
        j_ax = np.tile(np.linspace(-5, 5, 70), 70) #-5, -4.8,..., 5,..., -5

        normal_lookup = norm.pdf(i_ax, j_ax, self.sigma).reshape((self.s_res, self.s_res))
        bernoulli_lookup = binom.pmf(1, 1, 1 / (1 + np.exp(-i_ax)))

        if t == 0:
            for i in range(0, self.s_res):
                for j in range(0, self.s_res):
                    self.P[0, i, j, t] = (1 - bernoulli_lookup[i]) \
                                       * normal_lookup[i, j] * self.posterior[j]
                    self.P[1, i, j, t] = bernoulli_lookup[i] \
                                       * normal_lookup[i, j] * self.posterior[j]
                    self.P_naive[0, i, j] = self.P[0, i, j, t]
                    self.P_naive[1, i, j] = self.P[1, i, j, t]
        else:
            # calculate joint distribution for each entry in matrix
            # [p(o_t,s_t,s_t-1|o_t-1) = Bern(o_t;l(1_t)) * N(s_t;s_t-1;sigma) * p(s_t)]
            # k: all possible observations; i: distribution for s_t conditioned on j: values of s_t-1
            for i in range(0, self.s_res):
                for j in range(0, self.s_res):
                    self.P[0, i, j, t] = (1 - bernoulli_lookup[i]) \
                                         * normal_lookup[i, j] * self.posterior[j]
                    self.P[1, i, j, t] = bernoulli_lookup[i] \
                                         * normal_lookup[i, j] * self.posterior[j]
        # evaluate unobserved stimulus distribution
        if type == "SP":
            P_ij = self.P[self.sequence[t], :, :, t]
            P_ij_naive = self.P_naive[self.sequence[t], :, :]
        elif type == "AP":
            P_ij = self.P[self.repetition[t], :, :, t]
            P_ij_naive = self.P_naive[self.repetition[t], :, :]
        else:
            print("Choose a valid type!")

        # integration by summation
        P_sum_over_j = np.sum(P_ij, 1)
        P_sum_over_j_naive = np.sum(P_ij_naive, 1)

        P_sum_over_ij = np.sum(P_sum_over_j)
        P_sum_over_ij_naive = np.sum(P_sum_over_j_naive)

        P_sum_over_kij = np.sum(np.sum(np.sum(self.P[:, :, :, t], 0), 0), 0)

        # evaluate posterior
        posterior_lag = self.posterior[:]
        self.posterior = P_sum_over_j / P_sum_over_ij
        self.posterior_naive = P_sum_over_j_naive / P_sum_over_ij_naive
        self.predictive = P_sum_over_ij / P_sum_over_kij

        return posterior_lag


    def compute_surprisal(self, type):
        print("{}: Computing different surprisal measures for all {} timesteps.".format(type, self.T))

        results = []

        self.update_posterior(1, type)

        for t in range(2, self.T):
            # Loop over the full sequence and compute surprisal iteratively
            posterior_lag = self.update_posterior(t, type)
            PS_temp = self.predictive_surprisal()
            BS_temp = self.bayesian_surprisal(posterior_lag)
            CS_temp = self.corrected_surprisal(posterior_lag)
            temp = [t, self.sequence[t], self.hidden[t], PS_temp, BS_temp, CS_temp]
            results.append(temp)
        print("{}: Done computing surprisal measures for all {} timesteps.".format(type, self.T))
        return np.asarray(results)

    def predictive_surprisal(self):
        return -np.log(self.predictive)

    def bayesian_surprisal(self, posterior_lag):
        BS = mutual_info_score(posterior_lag, self.posterior)
        return BS

    def corrected_surprisal(self, posterior_lag):
        CS = mutual_info_score(posterior_lag, self.posterior_naive)
        return CS



def main(prob_regime_init, prob_regime_change,
         prob_obs_init, prob_obs_change, seq_length,
         sigma, s_min, s_max, s_res, model, save_results):
    # I: Generate binary sequence sampled from HHMM
    hhmm_temp = hhmm(prob_regime_init, prob_regime_change,
                     prob_obs_init, prob_obs_change)
    hhmm_seq = hhmm_temp.sample_seq(seq_length)[:, [1,2]]

    # II: Compute Surprisal for all time steps for Stimulus Prob BB Model
    BB_SBL_temp = SBL_GRW(hhmm_seq, sigma, s_min, s_max, s_res)
    results = BB_SBL_temp.compute_surprisal(model)

    if save_results:
        title = "sbl_surprise_" + str(model) + "_" + str(seq_length) + ".txt"
        np.savetxt(results_dir + title, results)



def test_agent(prob_regime_init, prob_regime_change,
               prob_obs_init, prob_obs_change, seq_length,
               sigma, s_min, s_max, s_res, model):
    # Test I: Generate binary sequence sampled from HHMM
    hhmm_temp = hhmm(prob_regime_init, prob_regime_change,
                     prob_obs_init, prob_obs_change)
    hhmm_seq = hhmm_temp.sample_seq(seq_length)[:, [1,2]]

    # Test IIa: Initialize SBL (seq, forgetting param), update posterior (t=3)
    GRW_SBL_temp = SBL_GRW(hhmm_seq, sigma, s_min, s_max, s_res)
    GRW_SBL_temp.update_posterior(2, model)
    print("---------------------------------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-reg_init', '--prob_regime_init', action="store", default=0.5, type=float,
						help="Initial regime probability")
    parser.add_argument('-reg_change', '--prob_regime_change', action="store", default=0.01, type=float,
						help="Probability of changing regime")
    parser.add_argument('-obs_init', '--prob_obs_init', action="store", default=0.5, type=float,
						help="Initial regime probability")
    parser.add_argument('-obs_change', '--prob_obs_change', action="store", default=0.25, type=float,
						help="Probability of changing regime")
    parser.add_argument('-seq', '--sequence_length', action="store", default=200, type=int,
						help='Length of binary sequence being processed')

    parser.add_argument('-sigma', '--sigma', action="store", default=2.5, type=float,
                        help='Step Size of GRW in latent space')
    parser.add_argument('-s_min', '--space_min', action="store", default=-5, type=float,
                        help='Min of Discretized Latent Space')
    parser.add_argument('-s_max', '--space_max', action="store", default=5, type=float,
                        help='Max of Discretized Latent Space')
    parser.add_argument('-s_res', '--space_res', action="store", default=70, type=float,
                        help='Bins/Values of Discretized Latent Space')

    parser.add_argument('-model', '--model', action="store", default="SP", type=str,
                        help='Gaussian Random Walk Probability Model (SP, AP, TP)')
    parser.add_argument('-T', '--test', action="store_true", help='Run tests.')
    parser.add_argument('-S', '--save', action="store_true", help='Save results to array.')

    args = parser.parse_args()

    prob_regime_init = np.array([args.prob_regime_init, 1-args.prob_regime_init])
    prob_regime_change = args.prob_regime_change
    prob_obs_init = np.array([args.prob_obs_init, 1-args.prob_obs_init, 0])
    prob_obs_change = args.prob_obs_change

    seq_length = args.sequence_length
    sigma = args.sigma
    s_min = args.space_min
    s_max = args.space_max
    s_res = args.space_res
    model = args.model

    run_test = args.test
    save_results = args.save

    hhmm_temp = hhmm(prob_regime_init=np.array([0.5, 0.5]),
                     prob_regime_change=0.01,
                     prob_obs_init=np.array([0.5, 0.5, 0]),
                     prob_obs_change=0.25)

    seq = hhmm_temp.sample_seq(10)

    if run_test:
        print("Started running basic tests.")
        test_agent(prob_regime_init, prob_regime_change,
                   prob_obs_init, prob_obs_change, seq_length,
                   sigma, s_min, s_max, s_res, model)

    else:
        start = time.time()
        main(prob_regime_init, prob_regime_change,
             prob_obs_init, prob_obs_change, seq_length,
             sigma, s_min, s_max, s_res, model, save_results)

        print("Done after {} secs".format(time.time() - start))
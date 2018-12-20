import os
import argparse
import numpy as np
from helpers import *


class SBL_Cat_Dir():
    """
    DESCRIPTION: Categorical Dirichlet Bayesian Sequential Learning Agent
        * Agent parses a binary sequence previously generated by HHMM
        * She updates her conjugate Cat-Dirichlet posterior with new evidence
        * She calculates different surprise measures as the come in
    INPUT: Binary Sequence and Exponentially Weighted forgetting parameter
    OUTPUT: Predictive surprisal, Bayesian surprisal, Confidence-corrected surprisal
    [t, o_t, s_t, Prediction_Surprise, Bayesian_Surprise, Confidence_Corrected_Surprise]
    """
    def __init__(self, seq, hidden, tau, model_type="SP", verbose=False):
        # Initialize SBL-learned sequence and exponential forgetting parameter
        self.sequence = seq.astype(int)
        self.hidden = hidden
        self.T = len(seq)

        self.type = model_type
        self.tau = tau
        self.verbose = verbose

        self.no_obs = np.unique(seq).shape[0]
        self.stim_ind = np.zeros((self.T, self.no_obs))

        # Construct matrix where col represents binary ind of specific stim at t
        for t in range(self.T):
            self.stim_ind[t, self.sequence[t]] = 1

        # AP: Generate T-dim vector indicating no-alternation from t-1 to t
        self.repetition = np.zeros(self.T)
        for t in range(1, self.T):
            if self.sequence[t] == self.sequence[t-1]:
                self.repetition[t] = 1

        # TP: Generate T-dim vectors indicating transition from state i
        self.transitions = np.zeros((self.T, self.no_obs))
        for t in range(1, self.T):
            self.transitions[t, 0] = (self.sequence[t-1] == 0)
            self.transitions[t, 1] = (self.sequence[t-1] == 1)
            self.transitions[t, 2] = (self.sequence[t-1] == 2)

        # Generate one T matrix with all discounting values
        self.exp_forgetting = np.exp(-self.tau*np.arange(self.T)[::-1])

        if self.type == "SP":
            self.alphas = np.ones(self.no_obs)
        elif self.type == "AP":
            self.alphas = np.ones(2)
        elif self.type == "TP":
            self.alphas = np.ones((self.no_obs, self.no_obs))
        else:
            raise Exception, "Provide right model type (SP, AP, TP)"


    def update_posterior(self):
        exp_weighting = self.exp_forgetting[-(self.t+1):]

        if self.type == "SP":
            for i in range(self.no_obs):
                self.alphas[i] = 1 + np.dot(exp_weighting, self.stim_ind[:self.t+1, i])

        elif self.type == "AP":
            if self.t == 0:
                print("Can't update posterior with only one observation - need two!")
                self.alphas[0] = 1
                self.alphas[1] = 1
            else:
                self.alphas[0] = 1 + np.dot(exp_weighting, self.repetition[:self.t+1])
                self.alphas[1] = 1 + np.dot(exp_weighting, 1-self.repetition[:self.t+1])

        elif self.type == "TP":
            # print(self.sequence[:t], self.transition_from_0[:t], self.transition_from_1[:t])
            if self.t == 0:
                print("Can't update posterior with only one observation - need two!")
                self.alphas = np.ones((self.no_obs, self.no_obs))
            else:
                for i in range(self.no_obs):
                    for j in range(self.no_obs):
                        # from-to alphas
                        self.alphas[i, j] = 1 + np.dot(exp_weighting, self.stim_ind[:self.t+1, j]*self.transitions[:self.t+1, i])

    def posterior_predictive(self, alphas):
        return np.array([alpha/self.alphas.sum(axis=0) for alpha in self.alphas])

    def naive_posterior(self, alphas):
        return self.posterior_predictive(alphas)/self.posterior_predictive(alphas).sum(axis=0)

    def predictive_surprisal(self, alphas, ind):
        return -np.log(self.posterior_predictive(alphas)[ind])

    def bayesian_surprisal(self, alphas_old, alphas):
        return kl_dir(alphas_old, alphas)

    def corrected_surprisal(self, alphas):
        return kl_dir(self.naive_posterior(alphas), alphas)

    def compute_surprisal(self, max_T, verbose_surprisal=False):
        print("{}: Computing different surprisal measures for {} timesteps.".format(self.type, max_T))
        results = []

        for t in range(max_T):
            # Loop over the full sequence and compute surprisal iteratively
            alphas_old = self.alphas.copy()
            self.t = t
            self.update_posterior()

            if self.type == "SP":
                ind = int(self.sequence[self.t])
            elif self.type == "AP":
                ind = int(self.repetition[self.t])
            elif self.type == "TP":
                # from and to stimulus transition
                ind = (np.argmax(self.transitions[self.t, :]), np.argmax(self.stim_ind[self.t, :]))
            else:
                raise Exception, "Provide right model type (SP, AP, TP)"

            PS_temp = self.predictive_surprisal(self.alphas, ind)
            BS_temp = self.bayesian_surprisal(alphas_old, self.alphas)
            CS_temp = self.corrected_surprisal(self.alphas)

            if verbose_surprisal:
                print("{} - t={}: PS={}, BS={}, CS={}".format(self.type, t+1, round(PS_temp, 4),  round(BS_temp, 4), round(CS_temp, 4)))
            # print(self.alphas)
            # print(alphas_old)
            # print(PS_temp, BS_temp, CS_temp)

            temp = [t, self.sequence[t], self.hidden[t], PS_temp, BS_temp, CS_temp]
            distr_params = list(self.alphas.reshape(1, -1)[0])
            results.append(temp + distr_params)
        print("{}: Done computing surprisal measures for all {} timesteps.".format(self.type, self.T))
        return np.asarray(results)


def main(seq, hidden, tau, model_type,
         prob_regime_init, prob_obs_init, prob_obs_change, prob_regime_change,
         save_results=False, title="temp", verbose=False):
    # II: Compute Surprisal for all time steps for Stimulus Prob CatDir Model
    CD_SBL_temp = SBL_Cat_Dir(seq, hidden, tau, model_type, verbose)
    results = CD_SBL_temp.compute_surprisal(max_T=CD_SBL_temp.T)

    time = results[:,0]
    sequence = results[:, 1]
    hidden = results[:, 2]
    PS = results[:, 2]
    BS = results[:, 3]
    CS = results[:, 4]

    results_formatted = {"time": time,
                         "sequence": sequence,
                         "hidden": hidden,
                         "predictive_surprise": PS,
                         "bayesian_surprise": BS,
                         "confidence_corrected_surprise": CS,
                         "prob_regime_init": prob_regime_init,
                         "prob_obs_init": prob_obs_init,
                         "prob_obs_change": prob_obs_change,
                         "prob_regime_change": prob_regime_change}

    if save_results:
        save_obj(results_formatted, results_dir + title)
        print("Saved in File: {}".format(results_dir + title))


def test_agent(seq, hidden, tau, model_type, verbose=False):
    # Test IIa: Initialize SBL (seq, forgetting param), update posterior (t=3)
    CD_SBL_temp = SBL_Cat_Dir(seq, hidden, tau=0., model_type=model_type)
    CD_SBL_temp.t = 2
    CD_SBL_temp.update_posterior()
    print("---------------------------------------------")
    print("{}: Dirichlet-Distribution after 3 timestep: alphas = {}".format(model_type, CD_SBL_temp.alphas))
    # Test IIb: Compute Surprisal once (SP, t=3)
    CD_SBL_temp.compute_surprisal(max_T=3, verbose_surprisal=True)
    # print("---------------------------------------------")
    # # Test IIc: Compute Surprisal for all time steps for Stimulus Prob BB Model
    # results = CD_SBL_temp.compute_surprisal(max_T=CD_SBL_temp.T)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-file', '--sample_file', action="store",
                        default="temporary_sample_title", type=str,
                        help='Title of file in which sequence in stored')
    parser.add_argument('-tau', '--forget_param', action="store",
                        default=0., type=float,
                        help='Exponentially weighting parameter for memory/posterior updating')
    parser.add_argument('-model', '--model', action="store", default="SP",
                        type=str,
                        help='Categorical Dirichlet Probability Model (SP, AP, TP)')
    parser.add_argument('-pkl_in', '--pickle', action="store_true", help='Load matlab sequence file.')
    parser.add_argument('-T', '--test', action="store_true", help='Run tests.')
    parser.add_argument('-S', '--save', action="store_true", help='Save results to array.')
    parser.add_argument('-v', '--verbose',
                        action="store_true",
                        default=False,
						help='Get status printed out')

    args = parser.parse_args()

    if args.pickle:
        sample = load_obj(results_dir + args.sample_file + ".pkl")
    else:
        sample = load_obj(results_dir + args.sample_file + ".mat")

    seq = sample["sample_output"][:, 2]
    hidden = sample["sample_output"][:, 1]

    prob_regime_init = sample["prob_regime_init"]
    prob_obs_init = sample["prob_obs_init"]
    prob_obs_change = sample["prob_obs_change"]
    prob_regime_change = sample["prob_regime_change"]

    tau = args.forget_param
    model = args.model

    run_test = args.test
    save_results = args.save
    verbose = args.verbose

    if run_test:
        print("Started running basic tests.")
        test_agent(seq, hidden, tau, model, verbose)

    else:
        main(seq, hidden, tau, model,
             prob_regime_init, prob_obs_init, prob_obs_change,
             prob_regime_change,
             save_results, title="CD_" + model + "_" + args.sample_file,
             verbose=False)

    """
    How to run:
        pythonw seq_gen.py -t S1_800 -obs_change 0.75 0.15 0.85 0.25 0.5 0.75 0.25 0.5 -order 2 -matlab -seq 500
        pythonw sbl_cat_dir.py -file S1_800 -S -model SP
    """

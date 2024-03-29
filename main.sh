#!/bin/bash
#
#SBATCH -p valhala                  # partition (queue)
#SBATCH --qos=valhala
#SBATCH -N 1                      # number of nodes
#SBATCH -n 1                      # number of cores
##SBATCH --mem=2M                 # memory pool for all cores
#SBATCH -t 0-00:01                # time (D-HH:MM)
#SBATCH -o slurm.%N.%j.out        # STDOUT
#SBATCH -e slurm.%N.%j.err        # STDERR

python optimize_hyperparams.py -prog --strategy ddp --num_devices 2 --acc cpu
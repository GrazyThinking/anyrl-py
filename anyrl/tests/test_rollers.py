"""
Test various Roller implementations.
"""

import unittest

from anyrl.rollouts import BasicRoller, TruncatedRoller, Rollout
from anyrl.tests import SimpleEnv, SimpleModel, DummyBatchedEnv

class TruncatedRollerTest(unittest.TestCase):
    """
    Tests for TruncatedRoller.
    """
    def test_basic_equivalence(self):
        """
        Test that TruncatedRoller is equivalent to a
        BasicRoller when used with a single environment.
        """
        self._test_basic_equivalence_case(False, False)
        self._test_basic_equivalence_case(True, False)
        self._test_basic_equivalence_case(True, True)

    def test_truncation(self):
        """
        Test that sequence truncation works correctly for
        a batch of one environment.
        """
        self._test_truncation_case(False, False)
        self._test_truncation_case(True, False)
        self._test_truncation_case(True, True)

    def test_batch_equivalence(self):
        """
        Test that doing things in batches is equivalent to
        doing things one at a time.
        """
        self._test_batch_equivalence_case(False, False)
        self._test_batch_equivalence_case(True, False)
        self._test_batch_equivalence_case(True, True)

    def _test_basic_equivalence_case(self, stateful, state_tuple):
        """
        Test BasicRoller equivalence for a specific set of
        model settings.
        """
        env_fn = lambda: SimpleEnv(3, (4, 5), 'uint8')
        env = env_fn()
        model = SimpleModel(env.action_space.low.shape,
                            stateful=stateful,
                            state_tuple=state_tuple)
        basic_roller = BasicRoller(env, model, min_episodes=5)
        expected = basic_roller.rollouts()
        total_timesteps = sum([x.num_steps for x in expected])

        batched_env = DummyBatchedEnv([env_fn], 1)
        trunc_roller = TruncatedRoller(batched_env, model, total_timesteps)
        actual = trunc_roller.rollouts()
        _compare_rollout_batch(self, actual, expected)

    def _test_truncation_case(self, stateful, state_tuple):
        """
        Test rollout truncation and continuation for a
        specific set of model parameters.
        """
        env_fn = lambda: SimpleEnv(7, (5, 3), 'uint8')
        env = env_fn()
        model = SimpleModel(env.action_space.low.shape,
                            stateful=stateful,
                            state_tuple=state_tuple)
        basic_roller = BasicRoller(env, model, min_episodes=5)
        expected = basic_roller.rollouts()
        total_timesteps = sum([x.num_steps for x in expected])

        batched_env = DummyBatchedEnv([env_fn], 1)
        trunc_roller = TruncatedRoller(batched_env, model, total_timesteps//2 + 1)
        actual1 = trunc_roller.rollouts()
        self.assertTrue(actual1[-1].trunc_end)
        actual2 = trunc_roller.rollouts()
        expected1, expected2 = _artificial_truncation(expected,
                                                      len(actual1) - 1,
                                                      actual1[-1].num_steps)
        self.assertEqual(len(actual2), len(expected2)+1)
        actual2 = actual2[:-1]
        _compare_rollout_batch(self, actual1, expected1)
        _compare_rollout_batch(self, actual2, expected2)

    def _test_batch_equivalence_case(self, stateful, state_tuple):
        """
        Test that doing things in batches is consistent,
        given the model parameters.
        """
        env_fns = [lambda seed=x: SimpleEnv(seed, (5, 3), 'uint8') for x in range(15)]
        model = SimpleModel((5, 3),
                            stateful=stateful,
                            state_tuple=state_tuple)

        unbatched_rollouts = []
        for env_fn in env_fns:
            batched_env = DummyBatchedEnv([env_fn], 1)
            trunc_roller = TruncatedRoller(batched_env, model, 17)
            for _ in range(3):
                unbatched_rollouts.extend(trunc_roller.rollouts())

        batched_rollouts = []
        batched_env = DummyBatchedEnv(env_fns, 3)
        trunc_roller = TruncatedRoller(batched_env, model, 17)
        for _ in range(3):
            batched_rollouts.extend(trunc_roller.rollouts())

        _compare_rollout_batch(self, unbatched_rollouts, batched_rollouts,
                               ordered=False)

def _compare_rollout_batch(test, rs1, rs2, ordered=True):
    """
    Assert that batches of rollouts are the same.
    """
    test.assertEqual(len(rs1), len(rs2))
    if ordered:
        for rollout1, rollout2 in zip(rs1, rs2):
            test.assertEqual(_rollout_hash(rollout1), _rollout_hash(rollout2))
    else:
        hashes1 = [_rollout_hash(r) for r in rs1]
        hashes2 = [_rollout_hash(r) for r in rs2]
        for hash1 in hashes1:
            test.assertTrue(hash1 in hashes2)
            hashes2.remove(hash1)

def _rollout_hash(rollout):
    """
    Generate a string that uniquely identifies a rollout.
    """
    res = ''
    res += str(rollout.trunc_start)
    res += str(rollout.trunc_end)
    res += str(rollout.observations)
    res += str(rollout.rewards)
    for out in rollout.model_outs:
        res += 'output'
        for key in sorted(out.keys()):
            res += 'kv'
            res += key
            res += str(out[key])
    return res

def _artificial_truncation(rollouts, rollout_idx, timestep_idx):
    """
    Split up the rollouts into two batches by artificially
    truncating (and splitting) the given rollout before
    the given timestep.

    Returns (left_rollouts, right_rollouts)
    """
    to_split = rollouts[rollout_idx]
    left = Rollout(observations=to_split.observations[:timestep_idx+1],
                   model_outs=to_split.model_outs[:timestep_idx+1],
                   rewards=to_split.rewards[:timestep_idx],
                   start_state=to_split.start_state,
                   trunc_start=False,
                   trunc_end=True)
    right = Rollout(observations=to_split.observations[timestep_idx:],
                    model_outs=to_split.model_outs[timestep_idx:],
                    rewards=to_split.rewards[timestep_idx:],
                    start_state=to_split.model_outs[timestep_idx-1]['states'],
                    trunc_start=True,
                    trunc_end=False)
    return rollouts[:rollout_idx]+[left], [right]+rollouts[rollout_idx+1:]

if __name__ == '__main__':
    unittest.main()

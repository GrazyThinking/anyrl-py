"""
Tests for experience replay buffers.
"""

from collections import Counter
import unittest

import numpy as np

from anyrl.rollouts import PrioritizedReplayBuffer

class PrioritizedReplayTest(unittest.TestCase):
    """
    Tests for PrioritizedReplayBuffer.
    """
    def test_uniform_sampling(self):
        """
        Test the buffer when it's configured to sample
        uniformly.
        """
        np.random.seed(1337)
        buf = PrioritizedReplayBuffer(capacity=10, alpha=0, beta=1)
        for i in range(10):
            sample = {'obs': 0, 'action': 0, 'reward': 0, 'new_obs': 0, 'steps': 1, 'idx': i}
            buf.add_sample(sample)
        sampled_idxs = []
        for _ in range(10000):
            samples = buf.sample(3)
            sampled_idxs.extend([s['idx'] for s in samples])
            buf.update_weights(samples, [s['idx'] for s in samples])
        counts = Counter(sampled_idxs)
        for i in range(10):
            frac = counts[i] / len(sampled_idxs)
            self.assertGreater(frac, 0.09)
            self.assertLess(frac, 0.11)

    def test_prioritized_sampling(self):
        """
        Test the buffer in a simple prioritized setting.
        """
        np.random.seed(1337)
        buf = PrioritizedReplayBuffer(capacity=10, alpha=1.5, beta=1, epsilon=0.5)
        for i in range(10):
            sample = {'obs': 0, 'action': 0, 'reward': 0, 'new_obs': 0, 'steps': 1, 'idx': i}
            buf.add_sample(sample, init_weight=i)
        sampled_idxs = []
        for i in range(50000):
            for sample in buf.sample(3):
                sampled_idxs.append(sample['idx'])
        counts = Counter(sampled_idxs)
        probs = np.power(np.arange(10).astype('float64') + 0.5, 1.5)
        probs /= np.sum(probs)
        for i, prob in enumerate(probs):
            frac = counts[i] / len(sampled_idxs)
            self.assertGreater(frac, prob - 0.01)
            self.assertLess(frac, prob + 0.01)

    def test_simple_importance_sampling(self):
        """
        Test importance sampling when the buffer is never
        changed after the initial build-up.
        """
        np.random.seed(1337)
        buf = PrioritizedReplayBuffer(capacity=10, alpha=1.5, beta=1.3, epsilon=0.5)
        for i in range(10):
            sample = {'obs': 0, 'action': 0, 'reward': 0, 'new_obs': 0, 'steps': 1, 'idx': i}
            buf.add_sample(sample, init_weight=i)
        weights = np.power(np.arange(10).astype('float64') + 0.5, 1.5)
        weights /= np.sum(weights)
        weights = np.power(weights * len(weights), -1.3)
        weights /= np.max(weights)
        for i in range(1000):
            samples = buf.sample(3)
            for sample in samples:
                self.assertTrue(np.allclose(weights[sample['idx']], sample['weight']))

    def test_online_updates(self):
        """
        Test importance sampling when new samples are
        inserted and new errors are inserted.
        """
        buf = PrioritizedReplayBuffer(capacity=10, alpha=1.5, beta=0.5, epsilon=0.5)
        weights = []
        def _random_weight():
            return np.abs(np.random.normal())
        def _add_sample():
            sample = {'obs': 0, 'action': 0, 'reward': 0, 'new_obs': 0, 'steps': 1}
            weight = _random_weight()
            buf.add_sample(sample, init_weight=weight)
            weights.append(weight)
        for _ in range(5):
            _add_sample()
        for _ in range(1000):
            samples = buf.sample(3)
            importance = np.power(np.array(weights) + 0.5, 1.5) / np.sum(weights)
            importance = np.power(importance * len(importance), -0.5)
            importance /= np.max(importance)
            new_weights = []
            for sample in samples:
                self.assertTrue(np.allclose(importance[sample['id']], sample['weight']))
                weight = _random_weight()
                weights[sample['id']] = weight
                new_weights.append(weight)
            buf.update_weights(samples, new_weights)
            _add_sample()
            if len(weights) > 10:
                weights = weights[1:]

if __name__ == '__main__':
    unittest.main()

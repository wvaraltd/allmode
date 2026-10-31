import unittest
from unittest.mock import Mock
from system_service import CpuUsageSampler


class CpuHealthTests(unittest.TestCase):
    def sampler(self, rows):
        self.now=0
        self.reader=Mock(side_effect=rows)
        return CpuUsageSampler(self.reader,lambda:self.now)

    def test_first_sample_unknown_then_measured_percentage(self):
        sampler=self.sampler(['cpu 100 0 100 800 0 0 0 0','cpu 150 0 150 900 0 0 0 0'])
        self.assertIsNone(sampler.sample()['cpu_usage_percent'])
        self.now=2
        self.assertEqual(sampler.sample(),dict(cpu_usage_percent=50.0,cpu_usage_interval_seconds=2))

    def test_guest_counters_not_double_counted_and_iowait_idle(self):
        sampler=self.sampler(['cpu 100 0 0 800 100 0 0 0 50 0','cpu 150 0 0 900 150 0 0 0 100 0'])
        sampler.sample();self.now=2
        self.assertEqual(sampler.sample()['cpu_usage_percent'],25.0)

    def test_zero_and_full_usage_are_real_deltas(self):
        sampler=self.sampler(['cpu 0 0 0 100','cpu 0 0 0 200','cpu 100 0 0 200'])
        sampler.sample();self.now=1
        self.assertEqual(sampler.sample()['cpu_usage_percent'],0.0)
        self.now=2
        self.assertEqual(sampler.sample()['cpu_usage_percent'],100.0)

    def test_multiple_consumers_use_cache_without_more_reads(self):
        sampler=self.sampler(['cpu 0 0 0 100','cpu 100 0 0 200'])
        sampler.sample();self.now=1
        expected=sampler.sample();self.now=1.1
        for _ in range(10):self.assertEqual(sampler.sample(),expected)
        self.assertEqual(self.reader.call_count,2)

    def test_counter_reset_or_no_delta_is_unknown(self):
        sampler=self.sampler(['cpu 100 0 0 100','cpu 100 0 0 100','cpu 0 0 0 0'])
        sampler.sample();self.now=1
        self.assertIsNone(sampler.sample()['cpu_usage_percent']);self.now=2
        self.assertIsNone(sampler.sample()['cpu_usage_percent'])

    def test_unavailable_clears_old_value_and_requires_new_baseline(self):
        sampler=self.sampler(['cpu 0 0 0 100','cpu 100 0 0 200',OSError('missing'),'cpu 200 0 0 300'])
        sampler.sample();self.now=1
        self.assertEqual(sampler.sample()['cpu_usage_percent'],50.0);self.now=2
        self.assertIsNone(sampler.sample()['cpu_usage_percent']);self.now=3
        self.assertIsNone(sampler.sample()['cpu_usage_percent'])

    def test_invalid_counters_are_unknown(self):
        for row in ('','cpu0 1 2 3 4','cpu nope 1 2 3','cpu -1 0 0 4'):
            self.assertIsNone(CpuUsageSampler(lambda:row).sample()['cpu_usage_percent'])


if __name__=='__main__':unittest.main()

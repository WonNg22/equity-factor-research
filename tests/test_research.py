import unittest
import numpy as np
import pandas as pd
from data import DB, MONTHS
from research import drawdown, spread, hac_se
from stock_panel import signals, evaluate
import sqlite3


class ResearchTests(unittest.TestCase):
    def test_database_coverage(self):
        with sqlite3.connect(DB) as conn:
            counts = conn.execute("SELECT COUNT(*) FROM portfolios GROUP BY signal,size_q,signal_q").fetchall()
        self.assertEqual(len(counts),75)
        self.assertTrue(all(n==len(MONTHS) for n, in counts))

    def test_source_dates_and_units(self):
        with sqlite3.connect(DB) as conn:
            values = conn.execute("SELECT ret FROM portfolios WHERE month='2009-04' AND signal='Momentum' AND size_q=5 ORDER BY signal_q").fetchall()
        self.assertAlmostEqual(values[-1][0]-values[0][0],-0.296,places=3)

    def test_orientation(self):
        legs = {1:0.01,5:0.06}
        for signal in ("Reversal","Low volatility"):
            self.assertAlmostEqual(spread(legs,signal),-0.05)
        self.assertAlmostEqual(spread(legs,"Momentum"),0.05)

    def test_initial_loss(self):
        np.testing.assert_allclose(drawdown(pd.Series([-.2,.25,-.1])),[-.2,0,-.1])

    def test_hac_zero_lags(self):
        x = np.array([0,1,2,3])
        self.assertAlmostEqual(hac_se(x,0),x.std()/2)

    def test_formation_and_future_mutation(self):
        m = pd.period_range("2019-01",periods=14,freq="M")
        df = pd.DataFrame(dict(month=m,monthly_ret=[.01]*11+[.2,.3,.4],vol60=.15))
        before = signals(df)
        self.assertAlmostEqual(before.loc[m[11],"Momentum"],1.01**11-1)
        self.assertAlmostEqual(before.loc[m[11],"Reversal"],-.2)
        df.loc[12,"monthly_ret"] = -.9
        after = signals(df)
        pd.testing.assert_series_equal(before.loc[m[11]].drop("forward_ret"),
                                       after.loc[m[11]].drop("forward_ret"))
        self.assertEqual(after.loc[m[11],"forward_ret"],-.9)

    def test_missing_holding_return(self):
        p = pd.DataFrame(dict(month=["2019-01","2019-02"],security_id="A",
                              eligible=1,vol60=.1,monthly_ret=[.1,np.nan]))
        with self.assertRaisesRegex(ValueError,"Missing holding return"):
            evaluate(p)

    def test_rank_ic(self):
        rows = [dict(month=m,security_id=i,eligible=1,vol60=.1,
                     monthly_ret=i*.01*sign) for i in range(5)
                for m,sign in [("2020-01",1),("2020-02",-1)]]
        result = evaluate(pd.DataFrame(rows))
        self.assertAlmostEqual(result.iloc[0].rank_ic,1)

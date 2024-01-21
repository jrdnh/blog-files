# Created by jrdnh 2024-01-07
# jrdnh.github.io

from datetime import date
from itertools import islice, pairwise, takewhile

from models import RelativeDelta
from pydantic import Field
from utils import YF, FixedIntervalSeries, sumproduct


###########
# Class representing an apartment building financial model

class AvgMonthlyRentPSF(FixedIntervalSeries):
    """
    Average monthly rent per square foot.

    Args:
        initial_rent_psf: Initial monthly rent psf.
        rent_growth_rate: Annual rent growth rate.
    """

    initial_rent_psf: float
    rent_growth_rate: float

    def __call__(self, from_dt: date, to_dt: date):
        """Weighted avg rent psf from `from_dt` to `to_dt`."""
        period_amt = self.initial_rent_psf
        days_amt = 0  # numerator, sum(rent psf * days) for each (partial) period
        for i, (per_start, per_end) in enumerate(pairwise(self.periods())):
            if per_start >= to_dt:
                break
            # if after first period, increase period_amt by growth rate
            if i > 0:
                period_yf = YF.monthly(per_start, per_end)
                period_amt = period_amt * (1 + self.rent_growth_rate * period_yf)
            # calculate year fraction for period that overlaps with (from_dt, to_dt)
            yf = max(YF.monthly(max(per_start, from_dt), min(per_end, to_dt)), 0)
            days_amt += period_amt * yf
        return days_amt / YF.monthly(from_dt, to_dt)


class AvgVacancyRate(FixedIntervalSeries):
    """
    Average vacancy rate.

    Args:
        vacancy_rates: List of vacancy rates for each period (as determined by self.periods()).
            The last vacancy rate is carried forward indefinitely.
    """

    vacancy_rates: list[float] = Field(..., min_items=1)

    def periods(self):
        """Yields periods with `.freq` for `len(self.vacancy_rates)` periods, than final period ending `datetime.date.max`."""
        yield from islice(super().periods(), len(self.vacancy_rates))
        yield date.max

    def __call__(self, from_dt: date, to_dt: date):
        """Weighted avg vacancy rate from `from_dt` to `to_dt`. Extrapolates final vacancy rate indefinitely."""
        total_yf = 0
        vacancy_yf = 0
        for (per_start, per_end), vacancy_rate in zip(
            pairwise(self.periods()), self.vacancy_rates
        ):
            if per_start >= to_dt:
                break
            # calculate year fraction for period that overlaps with (from_dt, to_dt)
            yf = max(YF.monthly(max(per_start, from_dt), min(per_end, to_dt)), 0)
            total_yf += yf
            vacancy_yf += vacancy_rate * yf
        # Add remaining vacancy rate to vacancy_yf
        yf = max(YF.monthly(per_end, to_dt), 0)
        total_yf += yf
        vacancy_yf += vacancy_rate * yf
        return vacancy_yf / total_yf


class GrossPotentialRent(FixedIntervalSeries):
    sf: int  # square feet
    avg_monthly_rent_psf: AvgMonthlyRentPSF  # average monthly rent per square foot

    def __call__(self, from_dt: date, to_dt: date):
        """Revenue from but excluding `from_dt` to and including `to_dt`."""
        periods = pairwise(self.periods())
        total_rent = 0
        for per_start, per_end in takewhile(lambda per: per[0] < to_dt, periods):
            if per_end > from_dt:
                period_yf = YF.monthly(max(per_start, from_dt), min(per_end, to_dt))
                rent = (
                    self.sf * self.avg_monthly_rent_psf(from_dt, to_dt) * period_yf * 12
                )
                total_rent += rent
        return total_rent


class EffectiveGrossIncome(FixedIntervalSeries):
    avg_vacancy_rate: AvgVacancyRate
    gross_potential_rent: GrossPotentialRent

    def vacancy(self, from_dt: date, to_dt: date):
        """Vacancy from but excluding `from_dt` to and including `to_dt`."""
        return -sumproduct(
            from_dt, to_dt, self.gross_potential_rent, self.avg_vacancy_rate
        )

    def __call__(self, from_dt: date, to_dt: date):
        """Effective gross rent from but excluding `from_dt` to and including `to_dt`."""
        return self.gross_potential_rent(from_dt, to_dt) + self.vacancy(from_dt, to_dt)


class OperatingExpenses(FixedIntervalSeries):
    units: int
    initial_opex_pu: float  # initial annual operating expenses per unit
    opex_growth_rate: float  # annual opex growth rate

    def __call__(self, from_dt: date, to_dt: date):
        """Operating expenses from but excluding `from_dt` to and including `to_dt`."""
        accumulated_amt = 0
        period_amt = self.initial_opex_pu * self.units
        for i, (per_start, per_end) in enumerate(
            takewhile(lambda p: p[0] < to_dt, pairwise(self.periods()))
        ):
            if i > 0:
                period_yf = YF.monthly(per_start, per_end)
                period_amt = period_amt * (1 + self.opex_growth_rate * period_yf)
            accumulated_amt += period_amt * max(
                YF.monthly(max(per_start, from_dt), min(per_end, to_dt)), 0
            )
        return accumulated_amt


class RealEstateTaxes(FixedIntervalSeries):
    sf: int
    monthly_re_tax_psf: float  # monthly real estate taxes per square foot
    ret_growth_rate: float  # annual real estate tax growth rate

    def __call__(self, from_dt: date, to_dt: date):
        """Real estate taxes from but excluding `from_dt` to and including `to_dt`."""
        accumulated_amt = 0
        period_amt = self.monthly_re_tax_psf * self.sf * 12
        for i, (per_start, per_end) in enumerate(
            takewhile(lambda p: p[0] < to_dt, pairwise(self.periods()))
        ):
            if i > 0:
                period_amt = period_amt * (
                    1 + self.ret_growth_rate * YF.monthly(per_start, per_end)
                )
            accumulated_amt += period_amt * max(
                YF.monthly(max(per_start, from_dt), min(per_end, to_dt)), 0
            )
        return accumulated_amt


class ReplacementReserves(FixedIntervalSeries):
    units: int
    annual_reserves_pu: float  # annual replacement reserves per unit
    rr_growth_rate: float  # annual replacement reserves growth rate

    def __call__(self, from_dt: date, to_dt: date):
        """Replacement reserves from but excluding `from_dt` to and including `to_dt`."""
        accumulated_amt = 0
        period_amt = self.annual_reserves_pu * self.units
        for i, (per_start, per_end) in enumerate(
            takewhile(lambda p: p[0] < to_dt, pairwise(self.periods()))
        ):
            if i > 0:
                period_amt = period_amt * (
                    1 + self.rr_growth_rate * YF.monthly(per_start, per_end)
                )
            accumulated_amt += period_amt * max(
                YF.monthly(max(per_start, from_dt), min(per_end, to_dt)), 0
            )
        return accumulated_amt


class TotalExpenses(FixedIntervalSeries):
    operating_expenses: OperatingExpenses
    real_estate_taxes: RealEstateTaxes
    replacement_reserves: ReplacementReserves

    def __call__(self, from_date: date, to_date: date):
        """Total expenses from but excluding `from_dt` to and including `to_dt`."""
        return (
            self.operating_expenses(from_date, to_date)
            + self.real_estate_taxes(from_date, to_date)
            + self.replacement_reserves(from_date, to_date)
        )


class NetOperatingIncome(FixedIntervalSeries):
    effective_gross_income: EffectiveGrossIncome
    total_expenses: TotalExpenses

    def __call__(self, from_dt: date, to_dt: date):
        """Net operating income from but excluding `from_dt` to and including `to_dt`."""
        return self.effective_gross_income(from_dt, to_dt) + self.total_expenses(
            from_dt, to_dt
        )


###########
# Create an model instance
closing_date = date(2019, 12, 31)
sf = 180_000
units = 230

noi = NetOperatingIncome(
    ref_date=closing_date,
    freq=RelativeDelta(months=1),
    effective_gross_income=EffectiveGrossIncome(
        ref_date=closing_date,
        freq=RelativeDelta(months=1),
        gross_potential_rent=GrossPotentialRent(
            ref_date=closing_date,
            freq=RelativeDelta(months=1),
            sf=sf,
            avg_monthly_rent_psf=AvgMonthlyRentPSF(
                ref_date=closing_date,
                freq=RelativeDelta(months=1),
                initial_rent_psf=3.16,
                rent_growth_rate=0.02,
            ),
        ),
        avg_vacancy_rate=AvgVacancyRate(
            ref_date=closing_date,
            freq=RelativeDelta(months=6),
            vacancy_rates=[0.1, 0.075, 0.05],
        ),
    ),
    total_expenses=TotalExpenses(
        ref_date=closing_date,
        freq=RelativeDelta(years=1),
        operating_expenses=OperatingExpenses(
            ref_date=closing_date,
            freq=RelativeDelta(months=1),
            units=units,
            initial_opex_pu=-3_300,
            opex_growth_rate=0.02,
        ),
        real_estate_taxes=RealEstateTaxes(
            ref_date=closing_date,
            freq=RelativeDelta(months=6),
            sf=sf,
            monthly_re_tax_psf=-0.3,
            ret_growth_rate=0.02,
        ),
        replacement_reserves=ReplacementReserves(
            ref_date=closing_date,
            freq=RelativeDelta(months=1),
            units=units,
            annual_reserves_pu=-300,
            rr_growth_rate=0.02,
        ),
    ),
)

noi_json = noi.model_dump_json(indent=2)

# write json values to file
# with open("noi.json", "w") as f:
#     f.write(noi_json)

# Create model from json
import json
import urllib.request
# import this if you are in a different file/interpreter
# from companion import NetOperatingIncome 

url = 'https://gist.githubusercontent.com/jrdnh/377f13e0ed0e6ac975b5d36156dd27f5/raw/44bb448d60ff6aae9cc5f5d9472edf9e0c0b85d3/noi.json'
with urllib.request.urlopen(url) as response:
   noi = NetOperatingIncome.model_validate_json(response.read())


# Model results
if __name__ == '__main__':
    from datetime import date
    # noi over the first year
    noi(date(2019, 12, 31), date(2020, 12, 31))

    # average monthly rent psf between 2021-06-02 and 2023-09-27
    noi.effective_gross_income.gross_potential_rent.avg_monthly_rent_psf(date(2021, 6, 2), date(2023, 9, 27))

    periods = [p for p in pairwise(islice(noi.periods(), 121))]
    [noi(*p) for p in periods]


    # Display and export results
    from itertools import pairwise
    from utils import field_values, flatten
    from models import RelativeDelta

    ten_years_monthly = list(pairwise((date(2019, 12, 31) + RelativeDelta(months=1) * i for i in range(121))))
    pro_forma = flatten(field_values(noi, ten_years_monthly))
    print(json.dumps(pro_forma, indent=2))

    import pandas as pd

    df = pd.DataFrame(pro_forma, index=[p[1] for p in ten_years_monthly]).T
    # df.to_clipboard()
    # df.to_excel('pro_forma.xlsx')
    print(df)


    # Confirm serialization and validation work
    new_noi = NetOperatingIncome.model_validate_json(noi.model_dump_json())
    assert new_noi == noi

    noi.model_dump_json()
    noi.model_json_schema()

    # performance
    from time import perf_counter

    def duration():
        start = perf_counter()
        field_values(noi, ten_years_monthly)
        print((perf_counter() - start) * 1000, 'ms')

    duration()

    import cProfile
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()
    field_values(noi, ten_years_monthly)
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats('tottime')
    stats.print_stats(10)
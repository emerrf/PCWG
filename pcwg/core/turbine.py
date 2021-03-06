import math
import interpolators
import scipy.interpolate
import numpy as np
import pandas as pd

from ..core.status import Status


class FourCellRelaxationFactory(object):
    
    def __init__(self, lws_lti, lws_hti, hws_lti, hws_hti):

        self.lws_lti = lws_lti
        self.lws_hti = lws_hti
        self.hws_lti = hws_lti
        self.hws_hti = hws_hti
        
    def new_relaxation(self, inflection_point):
                
        return Relaxation(self.lws_lti,
                          self.lws_hti,
                          self.hws_lti,
                          self.hws_hti,
                          inflection_point)


class TwoCellRelaxationFactory(FourCellRelaxationFactory):
    def __init__(self, low_wind_speed, high_wind_speed):
        FourCellRelaxationFactory.__init__(self,
                                           lws_lti=low_wind_speed,
                                           lws_hti=low_wind_speed,
                                           hws_lti=high_wind_speed,
                                           hws_hti=high_wind_speed)

    def new_relaxation(self, inflection_point):
        return Relaxation(self.lws_lti, self.lws_hti, self.hws_lti, self.hws_hti, inflection_point)


class NoRelaxationFactory(object):

    def new_relaxation(self, inflection_point):

        # suppress unused parameter message in PyCharm
        _ = inflection_point

        return NoRelaxation()


class NoRelaxation(object):
    
    def relax(self, correction, wind_speed, reference_turbulence, target_turbulence):

        # supress unused parameter message in PyCharm
        _ = wind_speed
        _ = reference_turbulence
        _ = target_turbulence

        return correction


class InflectionPoint:

    def __init__(self, power_function, lower_wind_speed, upper_wind_speed, rated_power):
        self.value = self.calculate(power_function, lower_wind_speed, upper_wind_speed, rated_power)

    def calculate(self, power_function, lower_wind_speed, upper_wind_speed, rated_power):

        derivative = None
        previous_derivative = None
        wind_speed = 0.0
        delta = 0.1

        minimum_power = 0.25 * rated_power
        maximum_power = 0.75 * rated_power

        Status.add("Determining Power Curve Inflection Point")

        Status.add("LowerWindSpeed: {0}".format(lower_wind_speed), verbosity=2)
        Status.add("UpperWindSpeed: {0}".format(upper_wind_speed), verbosity=2)

        Status.add("WindSpeed SecondDerivative", verbosity=3)

        while wind_speed < upper_wind_speed:

            if wind_speed > lower_wind_speed:

                power = power_function(wind_speed)

                derivative = self.power_second_derivative(power_function, wind_speed, delta)

                Status.add("{0} {1}".format(wind_speed, derivative), verbosity=3)

                if minimum_power < power < maximum_power:
                    if previous_derivative is not None:
                        if abs(derivative) > 0.0 and abs(previous_derivative) > 0.0:
                            if (derivative * previous_derivative) < 0.0:
                                Status.add("Inflection point found: {0}".format(wind_speed))
                                return wind_speed

            wind_speed += delta
            previous_derivative = derivative

        raise Exception("Cannot calculate inflection point:\n"
                        "lower wind speed: {0}\n"
                        "upper wind speed: {1}\n"
                        "derivative: {2}\n"
                        "previous derivative: {3}\n"
                        .format(lower_wind_speed, upper_wind_speed, derivative, previous_derivative))

    def power_second_derivative(self, power_function, wind_speed, delta):

        wind_speed_m = wind_speed - delta
        wind_speed_p = wind_speed + delta

        derivative_m = self.power_derivative(power_function, wind_speed_m, delta)
        derivative_p = self.power_derivative(power_function, wind_speed_p, delta)

        return (derivative_p - derivative_m) / (wind_speed_p - wind_speed_m)

    def power_derivative(self, power_function, wind_speed, delta):

        wind_speed_m = wind_speed - delta
        wind_speed_p = wind_speed + delta

        power_m = power_function(wind_speed_m)
        power_p = power_function(wind_speed_p)

        return (power_p - power_m) / (wind_speed_p - wind_speed_m)


class Relaxation(object):
    
    def __init__(self, lws_lti, lws_hti, hws_lti, hws_hti, inflection_point):
        
        self.lws_lti = lws_lti
        self.lws_hti = lws_hti
        self.hws_lti = hws_lti
        self.hws_hti = hws_hti

        self.inflection_point = inflection_point
        Status.add("Inflection point: {0}".format(self.inflection_point), verbosity=3)

    def relax(self, correction, wind_speed, reference_turbulence, target_turbulence):
        
        if target_turbulence > reference_turbulence:
            if wind_speed > self.inflection_point:
                return (1.0 - self.hws_hti) * correction
            else:
                return (1.0 - self.lws_hti) * correction
        else:
            if wind_speed > self.inflection_point:
                return (1.0 - self.hws_lti) * correction
            else:
                return (1.0 - self.lws_lti) * correction
                


class PowerCurve(object):

    def __init__(self,
                 rotor_geometry,
                 reference_density,
                 data_frame,
                 wind_speed_column,
                 turbulence_column,
                 power_column,
                 count_column=None,
                 rated_power=None,
                 name='Undefined',
                 interpolation_mode='Cubic Spline',
                 zero_ti_pc_required=False,
                 x_limits=None,
                 sub_power=None,
                 relaxation_factory=NoRelaxationFactory()):
                
        self.name = name
        self.interpolation_mode = interpolation_mode

        self.reference_density = reference_density
        self.data_frame = data_frame

        self.wind_speed_column = wind_speed_column
        self.turbulence_column = turbulence_column
        self.power_column = power_column
        self.count_column = count_column
        
        self.x_limits = x_limits
        self.sub_power = sub_power

        self.rotor_geometry = rotor_geometry
       
        if self.count_column is not None:
            self.hours = self.data_frame[count_column].sum()*1.0/6.0
        else:
            self.hours = None

        wind_data = data_frame[self.wind_speed_column]
        power_data = data_frame[self.power_column]

        self.first_wind_speed = min(wind_data)
        self.cut_in_wind_speed = self.calculate_cut_in_wind_speed()
        self.cut_out_wind_speed = self.calculate_cut_out_wind_speed()

        self.wind_speed_points, self.power_points = self.extract_points(wind_data, power_data)
        
        self.turbulence_function = self.create_one_dimensional_function(self.wind_speed_column,
                                                                        self.turbulence_column,
                                                                        supress_negative=True)

        self.available_power = AvailablePower(self.rotor_geometry, self.reference_density)

        Status.add("calculating power function ({0})".format(self.interpolation_mode), verbosity=3)
        self.power_function = self.create_power_function(self.wind_speed_points, self.power_points)
        Status.add("power function calculated ({0})".format(type(self.power_function)), verbosity=3)

        self.rated_power = self.get_rated_power(rated_power, data_frame[self.power_column])

        try:
            self.inflection_point = InflectionPoint(self.power_function,
                                                    self.cut_in_wind_speed,
                                                    self.cut_out_wind_speed,
                                                    self.rated_power).value
        except Exception as e:
            Status.add("Inflection point calculation failed: {0}".format(e), red=True)
            self.inflection_point = None

        self.set_relaxation_factory(relaxation_factory)

        self.zero_ti_pc_required = zero_ti_pc_required

    @property
    def zero_ti_pc_required(self): 
        return self._zero_ti_pc_required

    @zero_ti_pc_required.setter
    def zero_ti_pc_required(self, value): 

        if hasattr(self, '_zero_ti_pc_required'):
            update = (self._zero_ti_pc_required != value)
        else:
            update = True

        if update:

            if value and (self.reference_density is None):
                raise Exception("Zero Turbulence Curve cannot be calculated"
                                " if turbine does not have a well defined density")

            self._zero_ti_pc_required = value
            self.update_zero_ti()

    def get_raw_levels(self):
    
        padded_levels = (self.data_frame['Is Extrapolation'] == True)

        return self.data_frame[~padded_levels]

    def set_relaxation_factory(self, relaxation_factory):

        self.relaxation_factory = relaxation_factory

        self.relaxation = self.relaxation_factory.new_relaxation(self.inflection_point)

    def update_zero_ti(self, relaxation_factory=None):

        if relaxation_factory is not None:
            self.set_relaxation_factory(relaxation_factory)

        Status.add("Zero TI Required: {0}".format(self.zero_ti_pc_required), verbosity=3)
           
        if self.zero_ti_pc_required:

            Status.add("Calculating zero turbulence curve for {0} Power Curve".format(self.name), verbosity=3)
            
            try:            
                self.calculate_zero_turbulence_power_curve()
                Status.add("Calculation of zero turbulence curve for {0}"
                           " Power Curve successful".format(self.name), verbosity=3)
            except None as error:
                err_msg = "Calculation of zero turbulence curve for {0}" \
                          " Power Curve unsuccessful: {1}".format(self.name, error)
                raise Exception(err_msg)
                
        else:
            
            self.zeroTurbulencePowerCurve = None
            self.simulatedPower = None

        Status.add("Turbine Created Successfully", verbosity=3)

    def get_level(self, wind_speed, tolerance=0.00001):

        for i in range(len(self.wind_speed_points)):
            
            diff = abs(self.wind_speed_points[i] - wind_speed)

            if diff < tolerance:
                return self.power_points[i]

        raise Exception("Cannot find level: {0}".format(wind_speed))

    def calculate_zero_turbulence_power_curve(self):

        integration_range = IntegrationRange(0.0, 100.0, 0.1)

        wind_speeds = []
        powers = []
        turbulence_values = []
        
        for index in self.data_frame.index:

            wind_speed = self.data_frame.loc[index, self.wind_speed_column]
            power = self.data_frame.loc[index, self.power_column]
            turbulence = self.data_frame.loc[index, self.turbulence_column]

            if not np.isnan(wind_speed) and \
               not np.isnan(power) and \
               not np.isnan(turbulence) and \
               wind_speed >= 0.0 and \
               power >= 0.0 and \
               turbulence > 0:

                wind_speeds.append(wind_speed)
                turbulence_values.append(turbulence)
                powers.append(power)
        
        self.zeroTurbulencePowerCurve = ZeroTurbulencePowerCurve(wind_speeds,
                                                                 powers,
                                                                 turbulence_values,
                                                                 integration_range,
                                                                 self.available_power,
                                                                 self.reference_density,
                                                                 self.relaxation)

        self.simulatedPower = SimulatedPower(self.zeroTurbulencePowerCurve, integration_range)

    def get_rated_power(self, rated_power, power_curve_levels):

        if rated_power is None:
            return power_curve_levels.max()
        else:
            return rated_power

    def get_threshold_wind_speed(self):
        return float(interpolators.LinearPowerCurveInterpolator(self.power_points, self.wind_speed_points,
                                                                self.rated_power)(0.85 * self.rated_power) * 1.5)

    def get_turbulence_levels(self, power_curve_levels, turbulence_levels, fixed_turbulence):

        if fixed_turbulence is not None:

            turbulence_levels = pd.Series(index=power_curve_levels.index)
            
            for level in power_curve_levels.index:
                turbulence_levels[level] = fixed_turbulence
            
        else:

            turbulence_levels = turbulence_levels

        return turbulence_levels

    def create_one_dimensional_function(self, x_col, y_col, supress_negative=True):

        x, y = [], []

        for index in self.data_frame.index:

            x_value = self.data_frame.loc[index, x_col]
            y_value = self.data_frame.loc[index, y_col]

            if (not np.isnan(x_value)) and (not np.isnan(y_value)):
                if (not supress_negative) or y_value > 0:
                    x.append(x_value)        
                    y.append(y_value)

        return interpolators.LinearTurbulenceInterpolator(x, y)        
        
    def extract_points(self, x_data, y_data):

        if x_data is None:
            x_data = pd.Series(y_data.index, index=y_data.index)
        
        x, y = [], []

        Status.add("Preparing input points", verbosity=3)
        
        for i in y_data.index:
            
            if i in x_data.index and not np.isnan(x_data[i]):
                x_val = x_data[i]
            else:
                x_val = i

            y_val = y_data[i]

            if (not np.isnan(x_val)) and (not np.isnan(y_val)):
                x.append(x_val)
                y.append(y_val)

            Status.add("{0} {1} {2}".format(i, x[-1], y[-1]), verbosity=3)
        
        return x, y

    def create_power_function(self, x, y):
        
        Status.add("Creating interpolator", verbosity=3)
        
        if self.interpolation_mode == 'Linear':
            return interpolators.LinearPowerCurveInterpolator(x, y, self.cut_out_wind_speed)
        elif self.interpolation_mode == 'Cubic' or self.interpolation_mode == 'Cubic Spline':
            return interpolators.CubicSplinePowerCurveInterpolator(x, y, self.cut_out_wind_speed)
        elif self.interpolation_mode == 'Cubic Hermite':
            return interpolators.CubicHermitePowerCurveInterpolator(x, y, self.cut_out_wind_speed)
        elif self.interpolation_mode == 'Marmander' or self.interpolation_mode == 'Marmander (Cubic Spline)':
            return interpolators.MarmanderPowerCurveInterpolatorCubicSpline(x, y, self.cut_out_wind_speed,
                                                                 x_limits=self.x_limits,
                                                                 sub_power=self.sub_power)
        elif self.interpolation_mode == 'Marmander (Cubic Hermite)':
            return interpolators.MarmanderPowerCurveInterpolatorCubicHermite(x, y, self.cut_out_wind_speed,
                                                                 x_limits=self.x_limits,
                                                                 sub_power=self.sub_power)
        else:
            raise Exception('Unknown interpolation mode: {0}'.format(self.interpolation_mode))

    def power(self, wind_speed, turbulence=None, extra_turbulence_correction=False):

        reference_power = self.power_function(wind_speed)

        if turbulence is None:
            power = reference_power
        else:

            reference_turbulence = self.reference_turbulence(wind_speed)

            simulated_power_site = self.simulatedPower.power(wind_speed, turbulence)
            simulated_power_reference = self.simulatedPower.power(wind_speed, reference_turbulence)

            correction = simulated_power_site - simulated_power_reference

            relaxed_correction = self.relaxation.relax(correction,
                                               wind_speed,
                                               reference_turbulence,
                                               turbulence)

            power = reference_power + relaxed_correction

            if extra_turbulence_correction:
                power *= self.calculate_extra_turbulence_correction(wind_speed,
                                                                    turbulence,
                                                                    reference_turbulence)

        power = max([0.0, power])
        power = min([self.rated_power, power])

        return power

    def calculate_extra_turbulence_correction(self, wind_speed, turbulence, reference_turbulence):

        xprime = self.inflection_point - wind_speed
        tprime = (reference_turbulence - turbulence) / reference_turbulence

        if xprime < 0.0 or tprime < 0.0:
            return 1.0

        a = -0.02 * math.tanh(2.0 * tprime)
        b = -0.03 * (math.exp(1.5 * tprime) - 1.0)

        return 1.0 + a * xprime + b

    def reference_turbulence(self, wind_speed):
        if wind_speed < self.first_wind_speed:
            return self.turbulence_function(self.first_wind_speed)
        elif wind_speed > self.cut_out_wind_speed:
            return self.turbulence_function(self.cut_out_wind_speed)
        else:
            return self.turbulence_function(wind_speed)
            
    def calculate_cut_in_wind_speed(self):
        return min(self.non_zero_levels())
    
    def calculate_cut_out_wind_speed(self):
        return max(self.non_zero_levels())

    def non_zero_levels(self):

        levels = []

        for index in self.data_frame.index:

            power = self.data_frame.loc[index, self.power_column]
            speed = self.data_frame.loc[index, self.wind_speed_column]

            if not np.isnan(power) and power > 0.0:
                levels.append(speed)

        return levels

    def __str__(self):

        value = "Wind Speed\tPower\n"

        for wind_speed in self.wind_speed_points:
            value += "%0.2f\t%0.2f\n" % (wind_speed, self.power(wind_speed))

        return value


class RotorGeometry:

    def __init__(self, diameter, hub_height, tilt=None):

        if diameter is None:
            raise Exception('Diameter is not set')

        if hub_height is None:
            raise Exception('Hub Height is not set')

        self.diameter = diameter
        self.radius = diameter / 2
        self.area = math.pi * self.radius ** 2
        self.hub_height = hub_height
        self.lower_tip = self.hub_height - self.radius
        self.upper_tip = self.hub_height + self.radius
        self.tilt = tilt        

    def within_rotor(self, height):
        return (height > self.lower_tip) and (height < self.upper_tip)


class IntegrationProbabilities:

    def __init__(self, wind_speeds, wind_speed_step):

        # speed optimised normal distribution
        self.wind_speeds = wind_speeds
        self.a = wind_speed_step / math.sqrt(2.0 * math.pi)
                
    def probabilities(self, wind_speed_mean, wind_speed_std__dev):
        if wind_speed_std__dev == 0:
            return np.nan

        one_over_standard_deviation = 1.0 / wind_speed_std__dev
        one_over_standard_deviation_sq = one_over_standard_deviation * one_over_standard_deviation
        
        b = self.a * one_over_standard_deviation
        c = -0.5 * one_over_standard_deviation_sq
        
        wind_speed_minus_means = (self.wind_speeds - wind_speed_mean)
        wind_speed_minus_mean_sq = wind_speed_minus_means * wind_speed_minus_means

        d = c * wind_speed_minus_mean_sq

        return b * np.exp(d)


class IntegrationRange:

    def __init__(self, minimum_wind_speed, maximum_wind_speed, wind_speed_step):
        
        self.minimum_wind_speed = minimum_wind_speed
        self.maximum_wind_speed = maximum_wind_speed
        self.wind_speed_step = wind_speed_step
        self.wind_speeds = np.arange(minimum_wind_speed, maximum_wind_speed, wind_speed_step)

        self.integrationProbabilities = IntegrationProbabilities(self.wind_speeds, self.wind_speed_step)

    def probabilities(self, wind_speed_mean, wind_speed_std_dev):
        return self.integrationProbabilities.probabilities(wind_speed_mean, wind_speed_std_dev)


class AvailablePower(object):

    def __init__(self, rotor_geometry, density):
        
        self.area = rotor_geometry.area
        self.density = density
        
    def power(self, wind_speed):

        return 0.5 * self.density * self.area * wind_speed * wind_speed * wind_speed / 1000.0

    def power_coefficient(self, wind_speed, actual_power):

        return actual_power / self.power(wind_speed)


class ZeroTurbulencePowerCurve(object):

    def __init__(self,
                 reference_wind_speeds,
                 reference_powers,
                 reference_turbulence_values,
                 integration_range,
                 available_power,
                 density,
                 relaxation):

        self.integration_range = integration_range

        self.initial_zero_turbulence_power_curve = InitialZeroTurbulencePowerCurve(reference_wind_speeds,
                                                                                   reference_powers,
                                                                                   reference_turbulence_values,
                                                                                   integration_range,
                                                                                   available_power,
                                                                                   density)

        simulated_reference_power_curve = SimulatedPowerCurve(reference_wind_speeds,
                                                              self.initial_zero_turbulence_power_curve,
                                                              reference_turbulence_values,
                                                              integration_range)

        self.wind_speeds = reference_wind_speeds
        self.powers = []

        self.min_wind_speed = None
        self.last_wind_speed = None
        self.last_power = None

        for i in range(len(self.wind_speeds)):

            correct_to_zero_turbulence = (-simulated_reference_power_curve.powers[i]
                                          + self.initial_zero_turbulence_power_curve.powers[i])

            power = reference_powers[i] + relaxation.relax(correct_to_zero_turbulence,
                                                           self.wind_speeds[i],
                                                           reference_turbulence_values[i],
                                                           0.0)
            if reference_powers[i] > 0:
                if self.last_wind_speed is None or self.wind_speeds[i] > self.last_wind_speed:
                    self.last_wind_speed = self.wind_speeds[i]
                    self.last_power = power

            self.powers.append(power)

        self.powerFunction = scipy.interpolate.interp1d(self.wind_speeds, self.powers)
        
        self.min_wind_speed = min(self.wind_speeds)
        self.df_power_levels = pd.DataFrame(self.powers, index=self.wind_speeds, columns=['Power'])

    def power(self, wind_speed):
        
        if wind_speed < self.min_wind_speed:
            return 0.0
        elif wind_speed > self.last_wind_speed:
            return self.last_power
        else:
            return self.powerFunction(wind_speed)


class InitialZeroTurbulencePowerCurve(object):

    def __init__(self,
                 reference_wind_speeds,
                 reference_powers,
                 reference_turbulence_values,
                 integration_range,
                 available_power,
                 density):

        self.max_iterations = 5

        self.density = density

        self.integration_range = integration_range
        self.available_power = available_power
        self.reference_wind_speeds = reference_wind_speeds
        self.reference_powers = reference_powers
        self.reference_turbulence_values = reference_turbulence_values
        
        self.reference_power_curve_stats = IterationPowerCurveStats(reference_wind_speeds,
                                                                    reference_powers,
                                                                    available_power)

        self.selected_stats = self.solve(self.reference_power_curve_stats)

        selected_iteration = InitialZeroTurbulencePowerCurveIteration(reference_wind_speeds,
                                                                      self.available_power,
                                                                      self.selected_stats.rated_power,
                                                                      self.selected_stats.cut_in_wind_speed,
                                                                      self.selected_stats.cp_max,
                                                                      self.density)

        self.rated_wind_speed = selected_iteration.rated_wind_speed
        self.wind_speeds = selected_iteration.wind_speeds
        self.powers = selected_iteration.powers
        self.power = selected_iteration.power
        
    def solve(self, previous_iteration_stats, iteration_count=1):
        
        if iteration_count > self.max_iterations:
            raise Exception("Failed to solve initial zero turbulence curve in permitted number of iterations")

        previous_rated_power = previous_iteration_stats.rated_power
        previous_cut_in_wind_speed = previous_iteration_stats.cut_in_wind_speed
        previous_cp_max = previous_iteration_stats.cp_max

        iteration_zero_turbulence_curve = InitialZeroTurbulencePowerCurveIteration(self.integration_range.wind_speeds,
                                                                                   self.available_power,
                                                                                   previous_rated_power,
                                                                                   previous_cut_in_wind_speed,
                                                                                   previous_cp_max,
                                                                                   self.density)

        iteration_simulated_curve = SimulatedPowerCurve(self.reference_wind_speeds,
                                                        iteration_zero_turbulence_curve,
                                                        self.reference_turbulence_values,
                                                        self.integration_range)
                
        iteration_simulated_curve_stats = IterationPowerCurveStats(iteration_simulated_curve.wind_speeds,
                                                                   iteration_simulated_curve.powers,
                                                                   self.available_power)
        
        convergence_check = IterationPowerCurveConvergenceCheck(self.reference_power_curve_stats,
                                                                iteration_simulated_curve_stats)

        if convergence_check.isConverged:
            return previous_iteration_stats
        else:
            incremented_stats = IncrementedPowerCurveStats(previous_iteration_stats, convergence_check)
            return self.solve(incremented_stats, iteration_count + 1)


class IterationPowerCurveConvergenceCheck(object):

    def __init__(self, reference_stats, iteration_stats):

        self.threshold_power_diff = reference_stats.rated_power * 0.001
        self.threshold_cut_in_wind_speed_diff = 0.5
        self.threshold_cp_max_diff = 0.01

        self.rated_power_diff = iteration_stats.rated_power - reference_stats.rated_power
        self.cut_in_diff = iteration_stats.cut_in_wind_speed - reference_stats.cut_in_wind_speed
        self.cp_max_diff = iteration_stats.cp_max - reference_stats.cp_max

        self.rated_power_converged = abs(self.rated_power_diff) < self.threshold_power_diff
        self.cut_in_converged = abs(self.cut_in_diff) <= self.threshold_cut_in_wind_speed_diff
        self.cp_max_converged = abs(self.cp_max_diff) <= self.threshold_cp_max_diff

        self.isConverged = self.rated_power_converged and self.cut_in_converged and self.cp_max_converged


class IncrementedPowerCurveStats(object):

    def __init__(self, previous_iteration_stats, convergence_check):

        if convergence_check.rated_power_converged:
            self.rated_power = previous_iteration_stats.rated_power
        else:
            self.rated_power = previous_iteration_stats.rated_power - convergence_check.rated_power_diff

        if convergence_check.cut_in_converged:
            self.cut_in_wind_speed = previous_iteration_stats.cut_in_wind_speed
        else:
            self.cut_in_wind_speed = previous_iteration_stats.cut_in_wind_speed - convergence_check.cut_in_diff

        if convergence_check.cp_max_converged:
            self.cp_max = previous_iteration_stats.cp_max
        else:
            self.cp_max = previous_iteration_stats.cp_max - convergence_check.cp_max_diff


class InitialZeroTurbulencePowerCurveIteration(object):

    def __init__(self, wind_speeds, available_power, rated_power, cut_in_wind_speed, cp_max, density):

        self.wind_speeds = wind_speeds
        self.powers = []

        self.rated_wind_speed = ((2.0 * rated_power * 1000.0) /
                                 (density * cp_max * available_power.area)) ** (1.0 / 3.0)
        
        self.rated_power = rated_power
        self.cut_in_wind_speed = cut_in_wind_speed
        self.cp_max = cp_max
        
        self.availablePower = available_power
                
        for wind_speed in self.wind_speeds:
            self.powers.append(self.power(wind_speed))
        
    def power(self, wind_speed):

        if wind_speed > self.cut_in_wind_speed:
            if wind_speed < self.rated_wind_speed:
                return self.availablePower.power(wind_speed) * self.cp_max
            else:
                return self.rated_power
        else:
            return 0.0


class IterationPowerCurveStats(object):

    def __init__(self, wind_speeds, powers, available_power):

        self.rated_power = max(powers)
        
        threshold_power = self.rated_power * 0.001

        operating_wind_speeds = []
        cps = []

        for i in range(len(wind_speeds)):

            wind_speed = wind_speeds[i]
            power = powers[i]

            cps.append(available_power.power_coefficient(wind_speed, power))

            if power >= threshold_power:
                operating_wind_speeds.append(wind_speed)

        self.cp_max = max(cps)

        if len(operating_wind_speeds) > 0:
            self.cut_in_wind_speed = min(operating_wind_speeds)
        else:
            self.cut_in_wind_speed = 0.0
                  

class SimulatedPower(object):

    def __init__(self, zero_turbulence_power_curve, integration_range):
        
        self.zero_turbulence_power_curve = zero_turbulence_power_curve
        self.integration_range = integration_range
                
        integration_powers = []

        for wind_speed in np.nditer(self.integration_range.wind_speeds):
                integration_powers.append(self.zero_turbulence_power_curve.power(wind_speed))

        self.integrationPowers = np.array(integration_powers)
        
    def power(self, wind_speed, turbulence):
        standard_deviation = wind_speed * turbulence
        integration_probabilities = self.integration_range.probabilities(wind_speed, standard_deviation)
        return np.sum(integration_probabilities * self.integrationPowers) / np.sum(integration_probabilities)


class SimulatedPowerCurve(object):

    def __init__(self, wind_speeds, zero_turbulence_power_curve, turbulence_values, integration_range):

        simulated_power = SimulatedPower(zero_turbulence_power_curve, integration_range)

        self.wind_speeds = wind_speeds
        self.turbulence_values = turbulence_values
        self.powers = []

        for i in range(len(wind_speeds)):

            wind_speed = wind_speeds[i]
            turbulence = turbulence_values[i]
            
            power = simulated_power.power(wind_speed, turbulence)
            self.powers.append(power)

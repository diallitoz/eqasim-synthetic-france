import synthesis.population.spatial.secondary.rda as rda
import sklearn.neighbors
import scipy.spatial
import numpy as np

class CustomDistanceSampler(rda.FeasibleDistanceSampler):
    def __init__(self, random, distributions, maximum_iterations = 1000):
        rda.FeasibleDistanceSampler.__init__(self, random = random, maximum_iterations = maximum_iterations)

        self.random = random
        self.distributions = distributions

    def sample_distances(self, problem):
        distances = np.zeros((len(problem["modes"])))

        for index, (mode, travel_time) in enumerate(zip(problem["modes"], problem["travel_times"])):
            mode_distribution = self.distributions[mode]

            bound_index = np.count_nonzero(travel_time > mode_distribution["bounds"])
            mode_distribution = mode_distribution["distributions"][bound_index]

            distances[index] = mode_distribution["values"][
                np.count_nonzero(self.random.random() > mode_distribution["cdf"])
            ]

        return distances

class CandidateIndex:
    def __init__(self, data):
        self.data = data
        self.indices = {}

        for purpose, data_dict in self.data.items():
            print("Constructing spatial index for %s ..." % purpose)
            self.indices[purpose] = scipy.spatial.cKDTree(data_dict["locations"])

    def query(self, purpose, location):
        _, index = self.indices[purpose].query(location)
        identifier = self.data[purpose]["identifiers"][index]
        loc = self.data[purpose]["locations"][index]
        return identifier, loc

    def sample(self, purpose, random):
        index = random.integers(0, len(self.data[purpose]["locations"]))
        identifier = self.data[purpose]["identifiers"][index]
        loc = self.data[purpose]["locations"][index]
        return identifier, loc

class CustomDiscretizationSolver(rda.DiscretizationSolver):
    def __init__(self, index, random, escort_activities, escort_weights):
        self.index = index
        self.random = random
        self.escort_activities = np.array(escort_activities)
        self.escort_probs = np.array(escort_weights) / np.sum(escort_weights)

    def solve(self, problem, locations):
        discretized_locations = []
        discretized_identifiers = []

        for location, purpose in zip(locations, problem["purposes"]):
            if purpose == "escort":
                loc_purpose = str(self.random.choice(self.escort_activities, p=self.escort_probs))
            else:
                loc_purpose = purpose
            identifier, loc = self.index.query(loc_purpose, location)

            discretized_identifiers.append(identifier)
            discretized_locations.append(loc)

        assert len(discretized_locations) == problem["size"]

        return dict(
            valid = True, locations = np.vstack(discretized_locations), identifiers = discretized_identifiers
        )

class CustomFreeChainSolver(rda.RelaxationSolver):
    def __init__(self, random, index, escort_activities, escort_weights):
        self.random = random
        self.index = index
        self.escort_activities = np.array(escort_activities)
        self.escort_probs = np.array(escort_weights) / np.sum(escort_weights)

    def solve(self, problem, distances):
        purpose = problem["purposes"][0]

        if purpose == "escort":
            loc_purpose = str(self.random.choice(self.escort_activities, p=self.escort_probs))
        else:
            loc_purpose = purpose

        identifier, anchor = self.index.sample(loc_purpose, self.random)
        locations = rda.sample_tail(self.random, anchor, distances)
        locations = np.vstack((anchor, locations))

        assert len(locations) == len(distances) + 1
        return dict(valid = True, locations = locations, iterations = None)

import csv
import copy
import math
import statistics
import sys
import networkx as nx
from dataclasses import dataclass
from typing import Set

"""
Alayna Richmond
Northwestern University
Original: April 25, 2020
Edited: February 28, 2021

Overview:

This script creates pairings for a one-on-one career mentorship program run at
Northwestern University in the spring of 2020. It matches each underclassman mentee
to an upperclassman mentor who has experience with the tech recruitment process.
This program creates matches using responses to a survey that asked mentees about
their interests and mentors about their career experiences.

The program uses 3 factors to match mentees and mentors:
1. One goal of the mentorship program was to help mentees learn about different career
   paths and get a better idea of which field they may want to pursue. To accomplish this,
   our matching algorithm assigns each underclassman a mentor who has experience in some
   of the fields they are interested in.

2. A second goal of the program was for mentees to receive help with areas of recruitment
   such as resume building, technical interviews, and personal projects. The survey asked
   mentees which topics they wanted help with and asked mentors which topics they felt
   comfortable assisting with. The algorithm matches mentees with mentors who have the
   right expertise.

3. The last critera is that the mentor be at least one grade older than the mentee. Some
   upperclassmen signed up as mentees, and some sophmores signed up as mentors, so this
   needed to be enforced by the algorithm.


Implementation:

This script uses maximum complete bipartite matching in order to pair mentors with mentees.
It runs the following steps:

1. Parse survey responses
    - Extract values about the matching factors (career paths, recruitment topics, etc.)

2. Create a complete bipartite graph where
    - Mentees form one set
    - Mentors form another set
    - There is an edge between every mentee and every mentor
    - The weight of each edge is higher if the pairing is more favorable

3. Run maximum bipartite matching on the graph
    - The selected edges are the final mentor-mentee pairs

4. Output the pairings into a spreadsheet


Notes:

Since fewer mentors signed up than mentees, many upperclassmen were matched with multiple
underclassmen. The survey asked each mentor how many hours they could devote to the program,
and the script uses the answer to determine the max number of students they can mentor. The
script also ensures that upperclassmen are assigned the minimum number of mentees possible.
In other words, one upperclassmen will not be assigned 3 mentees and another assigned 1 if
both have time for 2.

Out-of-the-box bipartite matching algorithms do not have support for many-to-one matching.
To get around this, the script puts multiple nodes into the graph for any mentor who can
take on multiple mentees. Then the bipartite matching algorithm runs as is.


Running the script:

1. Perform the following steps from the folder containing this file.

2. Download the survey responses spreadsheet from Google Forms and place it in this folder.

    https://docs.google.com/forms/d/1UavWkzNOr8H7lFvsQFKBNXyGzndaAOOt_msFOy7jrBE/edit

3. Create and activate a virtual environment.

    pip install virtualenv     # installs virtualenv if you don't have it yet
    python3 -m venv env        # stores the virtual environment in a folder named env
    source env/bin/activate    # activates the virtual environment

4. Install the packages from requirements.txt

    pip install -r requirements.txt

5. Run the script with the following command:

    python3 matching_code.py <survey_responses_filename> <final_matches_filename>

6. Deactivate the virtual environment.

    deactivate


Relevant documentation:

https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment
https://docs.python.org/3/library/dataclasses.html
https://networkx.org/documentation/stable/tutorial.html
https://networkx.org/documentation/stable/reference/algorithms/bipartite.html
https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.bipartite.matching.minimum_weight_full_matching.html
"""


### Constants ###

DEBUG = True

# Indices into the survey response spreadsheet
# eg. EMAIL = 1 means that students' emails are located in the column with index 1
EMAIL = 1
ROLE = 2
MENTOR_ROLES = 3
MENTOR_available_time = 5
MENTOR_EXPERIENCED_FIELDS = 6
MENTOR_KNOWLEDGEABLE_TOPICS = 7
MENTEE_ROLES = 9
MENTEE_DESIRED_TOPICS = 10
MENTEE_INTERESTED_FIELDS = 11
YEAR = 13

# Multiple choice snswers to the survey question asking students if they want to be
# a mentor or mentee
MENTOR_ROLE = "Mentor"
MENTEE_ROLE = "Mentee"

# Numerical values for each year of college
# Used for checking whether the mentor is older than the mentee
YEAR_VALUES = { "Freshman": 1, "Sophomore": 2, "Junior": 3, "Senior": 4, "Masters": 4, "Alum": 5 }


### Data classes ###

@dataclass
class Student:

    """
    !!! Add any new fields that apply to both mentors and mentees !!!
    """

    email: str
    year: str
    
    @staticmethod
    def from_survey_response(row):
        """
        Creates a Student instance from a student's response to the sign-up form.
        row - list of answers (one row of the response spreadsheet)

        !!! When adding new fields to the Student class, add parsing code here !!!
        """
        email = row[EMAIL]
        year = row[YEAR]

        return Student(email, year)
    

@dataclass(unsafe_hash=True)
class Mentee(Student):

    """
    !!! Add any new fields that apply only to mentees !!!
    """

    # Which fields / career paths the mentee wants to learn more about
    interested_fields: Set[str]

    # Which areas of the recruitment process the mentee wants help with
    desired_topics: Set[str]

    def __init__(self, student):
        """
        Creates a Mentee by copying the fields from a Student instance.
        """
        self.__dict__.update(student.__dict__)

    @staticmethod
    def from_survey_response(row):
        """
        Creates a Mentee instance from a mentee's response to the sign-up form.
        row - list of answers (one row of the response spreadsheet)

        !!! When adding new fields to the Mentee class, add parsing code here !!!
        """

        student = Student.from_survey_response(row)
        mentee = Mentee(student)

        mentee.interested_fields = frozenset(row[MENTEE_INTERESTED_FIELDS].split(";"))
        mentee.desired_topics = frozenset(row[MENTEE_DESIRED_TOPICS].split(";"))

        return mentee


@dataclass(unsafe_hash=True)
class Mentor(Student):

    """
    !!! Add any new fields that apply only to mentors !!!
    """

    # Which fields / career paths the mentor has done an internship or personal project in
    experienced_fields: Set[str]

    # Which areas of the recruitment process the mentor is comfortable helping with
    knowledgeable_topics: Set[str]

    # Hours per week the mentor is able to dedicate
    available_time: int

    # When there are multiple instances of the same mentor, this field distinguishes
    # between copies. It ranges from 0 to number of instances - 1. See the introduction
    # for why this script creates duplicate instances.
    copy_number: int = 0

    def __init__(self, student):
        """
        Creates a Mentor by copying the fields from a Student instance.
        """
        self.__dict__.update(student.__dict__)

    @staticmethod
    def from_survey_response(row):
        """
        Creates a Mentor instance from a mentor's response to the sign-up form.
        row - list of answers (one row of the response spreadsheet)

        !!! When adding new fields to the Mentor class, add parsing code here !!!
        """

        student = Student.from_survey_response(row)
        mentor = Mentor(student)

        mentor.experienced_fields = frozenset(row[MENTOR_EXPERIENCED_FIELDS].split(";"))
        mentor.knowledgeable_topics = frozenset(row[MENTOR_KNOWLEDGEABLE_TOPICS].split(";"))

        # Note that when the survey asked mentors how many hours they were available, it
        # didn't require a numerical response (oops). Some students answered with more than
        # a simple number. The spreadsheet was edited to make all answers numbers before
        # running the code. In the future, we should always use Google Form's validation
        # feature.
        try:
            mentor.available_time = int(row[MENTOR_available_time])
        except ValueError:
            # Some mentors didn't answer the question
            mentor.available_time = 1

        return mentor

    # TODO: change the sign-up form to explicitly ask mentors how many mentees they can take on.
    # Make sure to remove all usages of the available_time field, and change this function into
    # a simple field.
    @property
    def num_mentees_possible(self):
        """
        Determines how many mentees the mentor can be assigned to.

        The first iteration of the sign-up form was sent out before writing the matching code,
        so we didn't think this through. Ideally we would have told mentors the time commitment
        for a single mentee and asked how many they could take on. Instead, we asked for the
        number of hours they could commit to the program. This function turns converts the
        number of hours into a number of mentees.
        """

        if self.available_time <= 2:
            # This assumes 1 hour per week per mentee, but in hindsight, each mentee probably
            # requires a greater time commitment.
            return self.available_time
        else:
            # We don't want any mentor taking on more than 3 mentees.
            return 3


    def copy_self_for_bipartite_graph(self):
        """
        For a mentor to be matched with up to n mentees, the mentor must have n nodes
        in the bipartite graph. This function copies the Mentor instance so that the total
        number of instances equals the number of mentees they can take on.

        returns - a list containing the existing and new Mentor instances
        """
        duplicates = [self]
        for duplicate_number in range(1, self.num_mentees_possible):
            duplicate = copy.copy(self)
            duplicate.copy_number = duplicate_number
            duplicates.append(duplicate)

        return duplicates


def create_mentors_and_mentees_from_survey_responses(filename):
    """
    Creates mentor and mentee instances from the sign-up form responses.

    filename - name of the Google Form response spreadsheet
    returns - list of mentee instances, list of mentor instances
    """

    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')

        mentees = []
        mentors = []

        for row in reader:
            is_mentee = row[ROLE] == MENTEE_ROLE
            is_mentor = row[ROLE] == MENTOR_ROLE

            if is_mentee:
                mentee = Mentee.from_survey_response(row)
                mentees.append(mentee)

            elif is_mentor:
                mentor = Mentor.from_survey_response(row)
                mentors.append(mentor)

        return mentees, mentors


### Graph classes ###

class MentorshipEdge:
    """
    Represents a weighted edge in the mentorship graph.
    """

    def __init__(self, mentee, mentor):
        self.mentee = mentee
        self.mentor = mentor

        self._weight = None
        self._statistics = None

    @property
    def weight(self):
        """
        Returns the weight, or value, of a particular mentor-mentee pairing. A higher
        weight means the pairing is better.
        """

        if self._weight is None:
            self._weight, self._statistics = self.compute_weight_and_statistics()
        return self._weight

    @property
    def statistics(self):
        """
        Returns detailed information about how good this particular mentor-mentee pairing
        is. There is one statistic for each matching critera used to calculate the weight.
        """
        if self._statistics is None:
            self._weight, self._statistics = self.compute_weight_and_statistics()
        return self._statistics

    def compute_weight_and_statistics(self):
        """
        !!! Edit the constants based on which weighting factors are most important, and
        add code for any new matching criteria !!!

        It's also helpful to run the matching algorithm in debug mode and look at
        the overall statistics on how well the algorithm performed. Then tweak the
        the constants until you get a satisfactory output.
        """

        ### Weighting constants ###

        CAREER_INTERESTS_MULTIPLIER = 5
        RECRUITMENT_TOPICS_MULTIPLIER = 3
        MENTOR_NOT_OLDER_PENALTY = 10000000 # requires the mentor to be older
        MENTOR_CLOSE_IN_YEAR_BONUS = 1
        MENTOR_TAKES_ON_ANOTHER_MENTEE_PENALTY = 100

        ### Compute weight based on matching critera ###

        weight = 0
        statistics = {}

        # 1. Career interests
        num_interests_overlap = len(self.mentee.interested_fields & self.mentor.experienced_fields)
        num_mentee_interests = len(self.mentee.interested_fields)
        interests_overlap_fraction = num_interests_overlap / num_mentee_interests
        statistics["interests_overlap_fraction"] = interests_overlap_fraction
        weight += CAREER_INTERESTS_MULTIPLIER * interests_overlap_fraction

        # 2. Recruitment topics
        num_topics_overlap = len(self.mentee.desired_topics & self.mentor.knowledgeable_topics)
        num_mentee_topics = len(self.mentee.desired_topics)
        topics_overlap_fraction = num_topics_overlap / num_mentee_topics
        statistics['topics_overlap_fraction'] = topics_overlap_fraction
        weight += RECRUITMENT_TOPICS_MULTIPLIER * topics_overlap_fraction

        # 3. Year
        year_difference = YEAR_VALUES[self.mentor.year] - YEAR_VALUES[self.mentee.year]
        statistics['year_difference'] = year_difference

        # Ensure that the mentor is older
        if year_difference <= 0:
            weight -= MENTOR_NOT_OLDER_PENALTY

        # Prefer matches that are relatively close in year (ie. we'd rather not have a
        # freshman paired with a master's student because the mentor's experience will
        # be less relevant).
        if year_difference == 1 or year_difference == 2:
            weight += MENTOR_CLOSE_IN_YEAR_BONUS


        """ !!! Add any new matching criteria here !!! """


        ### Handle many-to-one matches ###

        # This line has the following effect:
        # - Match every mentor to one mentee
        # - If there are still unpaired mentees, assign every mentor who can take on
        #   another mentee
        # - Repeat until there are no mentees remaining
        #
        # This works by weighting edges containing duplicate mentor nodes low enough that
        # they won't be used unless necessary.
        weight -= MENTOR_TAKES_ON_ANOTHER_MENTEE_PENALTY * self.mentor.copy_number

        return weight, statistics


class MentorshipGraph:
    """
    A bipartite graph where the two sets of nodes are mentees and mentors. Each mentee
    appears exactly once in the graph. Mentors may appear multiples times. If a mentor
    can take on n mentees, they will have n nodes in the graph.
    """

    def __init__(self, mentees, mentors):
        self.graph = nx.Graph()

        # Add mentees
        self.mentee_nodes = mentees
        self.graph.add_nodes_from(self.mentee_nodes, bipartite=0)

        # Add mentors
        self.mentor_nodes = []
        for mentor in mentors:
            self.mentor_nodes.extend(mentor.copy_self_for_bipartite_graph())
        self.graph.add_nodes_from(self.mentor_nodes, bipartite=1)

        # Add an edge between every mentee and mentor
        for mentee in self.mentee_nodes:
            for mentor in self.mentor_nodes:
                edge = MentorshipEdge(mentee, mentor)
                # The NetworkX library only implements minimum weight matching, but we want
                # maximum weight matching. To accomplish this, we just negate the weights.
                self.graph.add_edge(mentee, mentor, mentorship_edge=edge, weight=(-edge.weight))

    def find_optimal_matches(self):
        """
        Returns a list of MentorshipEdges representing the optimal mentor-mentee assignments.
        """
        pairings = nx.bipartite.minimum_weight_full_matching(self.graph, self.mentee_nodes)
        edges = [
            self.graph.edges[key, value]["mentorship_edge"]
            for key, value in pairings.items()
            if type(key) is Mentee
        ]
        
        return edges
    
def print_overall_matching_statistics(edges):
    """
    Calculates statistics to assess how well the algorithm performed according to the
    matching criteria.

    For each criteria that was used to compute the weights, prints out the average and
    standard deviation across all pairings.
    """

    if not DEBUG:
        return
    
    overall_statistics = {}

    # For each matching criteria used to compute the weights
    for criteria_name in edges[0]._statistics.keys():
        # Calculate the average across all selected pairs
        avg = statistics.mean([edge._statistics[criteria_name] for edge in edges])
        overall_statistics[f'{criteria_name}_avg'] = avg

        # And calculate the standard deviation
        stddev = statistics.stdev([edge._statistics[criteria_name] for edge in edges])
        overall_statistics[f'{criteria_name}_stddev'] = stddev

    for statistic, value in overall_statistics.items():
        print(statistic, ":", value)
    print('')


def save_optimal_matches_to_csv(edges, filename):
    """
    Saves the matches to a spreadsheet that can be shared with students.
    Make sure to send out the version printed when DEBUG is False.
    """

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')   

        if DEBUG:

            """ !!! When adding new matching criteria, add to the debug output !!! """

            writer.writerow([
                "Mentee email",
                "Mentor email",
                "Interests overlap fraction",
                "Topics overlap fraction",
                "Year difference (mentor - mentee)",
                "Weight"
            ])

            for edge in edges:
                writer.writerow([
                    edge.mentee.email,
                    edge.mentor.email,
                    edge._statistics["interests_overlap_fraction"],
                    edge._statistics["topics_overlap_fraction"],
                    edge._statistics["year_difference"],
                    edge.weight,
                ])
        else:

            # TODO: add preferred names to the final matches spreadsheet

            writer.writerow([
                "Mentee email",
                "Mentor email"
            ])
            
            for edge in edges:
                writer.writerow([
                    edge.mentee.email,
                    edge.mentor.email
                ])
            

if __name__== "__main__":
    survey_responses_filename = sys.argv[1]
    matches_filename = sys.argv[2]

    mentees, mentors = create_mentors_and_mentees_from_survey_responses(survey_responses_filename)
    graph = MentorshipGraph(mentees, mentors)
    edges = graph.find_optimal_matches()
    save_optimal_matches_to_csv(edges, matches_filename)
    print_overall_matching_statistics(edges)

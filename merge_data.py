### Setting the environment
import pandas as pd
import os
import datetime as dt

def merge_data():
    ### Loading data

    ### From ckan output
    source_ckan = pd.read_csv('data/ckan_output.csv', parse_dates=['DateUpdated'])
    source_ckan['Source'] = 'ckan API'

    ### From google sheets
    source_gsheets = pd.read_csv('data/from_Google_Sheets.csv', parse_dates=['DateUpdated'])
    source_gsheets['Source'] = 'manual extraction'

    ### From scotgov csv
    source_scotgov = pd.read_csv('data/scotgov-datasets.csv')
    source_scotgov = source_scotgov.rename(columns={
                                                    'title':'Title',
                                                    'category':'OriginalTags',
                                                    'organization':'Owner',
                                                    'notes':'Description',
                                                    'date_created':'DateCreated',
                                                    'date_updated':'DateUpdated',
                                                    'url':'PageURL'
                                                    })
    source_scotgov['Source'] = 'manual extraction'
    source_scotgov['License'] = 'OGL3'

    ### From arcgis api
    source_arcgis = pd.DataFrame()
    folder = 'data/arcgis/'
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit('.',1)[1] == 'csv':
                source_arcgis = source_arcgis.append(pd.read_csv(folder + r'/' + filename, parse_dates=['DateUpdated']))
    source_arcgis['Source'] = 'arcgis API'

    ### From usmart api
    source_usmart = pd.DataFrame()
    folder = 'data/USMART/'
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit('.',1)[1] == 'csv':
                source_usmart = source_usmart.append(pd.read_csv(folder + r'/' + filename, parse_dates=['DateUpdated']))
    source_usmart['Source'] = 'USMART API'
    source_usmart['DateUpdated'] = source_usmart['DateUpdated'].apply(lambda x: x.replace(tzinfo=None))

    ## From DCAT
    source_dcat = pd.DataFrame()
    folder = 'data/dcat/'
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit('.',1)[1] == 'csv':
                source_dcat = source_dcat.append(pd.read_csv(folder + r'/' + filename, parse_dates=['DateUpdated']))
                #source_dcat['DateUpdated'] = source_dcat['DateUpdated'].dt.tz_convert(None)
    source_dcat['Source'] = 'DCAT feed'


    ### Combine all data into single table
    data = source_ckan.append([source_gsheets, source_arcgis, source_usmart, source_scotgov, source_dcat])
    data = data.reset_index(drop=True)

    ### Saves copy of data without cleaning - for analysis purposes
    data.to_csv('data/merged_output_untidy.csv', index=False)
    
    ### clean data
    data = clean_data(data)
    
    ### Output cleaned data to csv
    data.to_csv('data/merged_output.csv', index=False)

    return data

def clean_data(dataframe):
    """cleans data in a dataframe

    Args:
        dataframe (pd.dataframe): the name of the dataframe of data to clean

    Returns:
        dataframe: dataframe of cleaned data
    """
    ### to avoid confusion and avoid re-naming everything...
    data = dataframe

    ### Renaming entries to match
    owner_renames = {
                    'Aberdeen': 'Aberdeen City Council',
                    'Dundee': 'Dundee City Council',
                    'Perth': 'Perth and Kinross Council',
                    'Stirling': 'Stirling Council',
                    'Angus': 'Angus Council',
                    'open.data@southayrshire':'South Ayrshire Council',
                    'SEPA': 'Scottish Environment Protection Agency',
                    'South Ayrshire': 'South Ayrshire Council',
                    'East Ayrshire': 'East Ayrshire Council',
                    'Highland Council GIS Organisation': 'Highland Council'
                    }
    data['Owner'] = data['Owner'].replace(owner_renames)
    ### Format dates as datetime type
    data['DateUpdated'] = pd.to_datetime(data['DateUpdated'], format='%Y-%m-%d', errors='coerce', utc=True).dt.date
    ### Inconsistencies in casing for FileType
    data['FileType'] = data['FileType'].str.upper()
    ### Creating a dummy column
    data['AssetStatus'] = None


    ### Cleaning dataset categories
    def tidy_categories(categories_string):
        """tidies the categories: removes commas, strips whitespace, converts all to lower and strips any trailing ";"

        Args:
            categories_string (string): the dataset categories as a string
        """
        tidied_string = str(categories_string).replace(',',';')
        tidied_list = [cat.lower().strip() for cat in tidied_string.split(';') if cat!=""]
        tidied_string=";".join(str(cat) for cat in tidied_list if str(cat)!='nan')
        if (len(tidied_string)>0):
            if (tidied_string[-1]==";"):
                tidied_string = tidied_string[:-1]
        return tidied_string

    ### Combining dataset categories
    def combine_categories(dataset_row):
        """Combine OriginalTags and ManualTags to get all tags

        Args:
            dataset_row (dataframe): one row of the dataset set
        """
        combined_tags = []
        if str(dataset_row['OriginalTags'])!='nan':
            combined_tags = combined_tags + str(dataset_row['OriginalTags']).split(';') 
        if str(dataset_row['ManualTags'])!='nan':
            combined_tags = combined_tags + str(dataset_row['ManualTags']).split(';')

        combined_tags = ";".join(str(cat) for cat in set(combined_tags))
        return combined_tags

    data['OriginalTags'] = data['OriginalTags'].apply(tidy_categories)
    data['ManualTags'] = data['ManualTags'].apply(tidy_categories)
    data['CombinedTags'] = data.apply(lambda x: combine_categories(x),axis=1)

    ### Creating new dataset categories for ODS
    def assign_ODScategories(categories_string):
        """Assigns one of ODS' 13 categories, or 'Uncategorised' if none.

        Args:
            categories_string (string): the dataset categories as a string
        """
        combined_tags = categories_string.split(';')

        ### Set association between dataset tag and ODS category
        ods_categories={
            'Arts / Culture / History':['arts','culture','history','military','art gallery','design','fashion','museum','historic centre','conservation', 'archaeology', 'events','theatre'],
            'Budget / Finance':['budget','finance','payment','grants','financial year', 'council tax'],
            'Economy':['economy','economic','economic activity','economic development','deprivation','scottish index of multiple deprivation','simd','business','estimated population','population','labour force'],
            'Education':['education','eductional','library','school meals','schools','school', 'nurseries', 'playgroups',],
            'Elections / Politics':['elections','politics','elecorate','election','electoral','electorate','local authority','council area','democracy','polling','lgcs democracy','democracy and governance','local government', 'councillor', 'councillors','community council'],
            'Environment':['environment','forest woodland strategy','waste','recycling','lgcs waste management','water-network', 'grafitti', 'street occupations', 'regeneration','vandalism','street cleansing', 'litter', 'toilets', 'drains','flytipping', 'flyposting','pollution', 'air quality', 'household waste', 'commercial waste'],
            'Food':['food','school meals','allotment'],
            'Health and Social Care':['health','human services', 'covid-19','covid','hospital','health board', 'health and social care partnership','medicine','health and social care','health and fitness','nhs24','hospital admissions','hospital mortality', 'mental health', 'pharmacy', 'GP', 'surgery','fostering','adoption', 'social work', 'asylum', 'immigration', 'citizenship', 'carers'],
            'Housing and Estates':['multiple occupation', 'housing', 'sheltered housing', 'adaptations', 'repairs', 'council housing', 'landlord', 'landlord registration', 'rent arrears', 'parking', 'garages', 'homelessness', 'temporary accommodation', 'rent', 'tenancy', 'housing advice', 'housing associations', 'housing advice', 'housing repairs', 'lettings','real estate','land records','land-cover','woodland','dwellings','burial grounds','cemeteries','property','vacant and derelict land','scottish vacant and derelict land','allotment'],
            'Law and Licensing':['law', 'licensing', 'regulation', 'regulations', 'licence', 'licenses', 'permit', 'permits', 'police', 'court', 'courts', 'tribunal', 'tribunals'],
            'Parks / Recreation':['parks','recreation','woodland','parks and open spaces'],
            'Planning / Zoning':['planning','zoning','council area','address','addresses','city development plan','boundaries','post-code','dwellings','planning permission','postcode-units','housing','property', 'building control', 'conservation'],
            'Public Safety':['emergency planning','public safety','crime and justice','lgcs community safety','street lighting','community safety','cctv','road safety'],
            'Tourism':['tourism','tourist','attractions','accomodation', 'historic buildings','tourist routes', 'cafes','restaurants', 'hotels','hotel'],
            'Transportation':['transportation','mobility','pedestrian','walking','walk','cycle','cycling','parking','car','bus','tram','train','taxi','transport','electric vehicle','electric vehicle charging points','transport / mobility','active travel','road safety','roads', 'community transport', 'road works', 'road closures','speed limits', 'port', 'harbour']
        }

        ### Return ODS if tag is a match
        applied_category = []
        for tag in combined_tags:
            for cat in ods_categories:
                if tag in ods_categories[cat]:
                    applied_category = applied_category + [cat]

        ### If no match, assign "Uncategorised". Tidy list of ODS categories into string.
        if len(applied_category) == 0:
            applied_category = ['Uncategorised']

        applied_category = ";".join(str(cat) for cat in set(applied_category))
        applied_category

        return applied_category

    ### Apply ODS categorisation
    data['ODSCategories'] = data['CombinedTags'].apply(assign_ODScategories)


    ### Tidy licence names
    def tidy_licence(licence_name):
        """ Temporary licence conversion to match export2jkan -- FOR ANALYTICS ONLY, will discard in 2022Q2 Milestone

        Returns:
            string: a tidied licence name
        """
        known_licences= {
                    'https://creativecommons.org/licenses/by-sa/3.0/': 'Creative Commons Attribution Share-Alike 3.0',
                    'Creative Commons Attribution 4.0':'Creative Commons Attribution 4.0',
                    'https://creativecommons.org/licenses/by/4.0/legalcode':'Creative Commons Attribution 4.0',
                    'OGL3':'Open Government Licence v3.0',
                    'Open Government Licence 3.0 (United Kingdom)':'Open Government Licence v3.0',
                    'UK Open Government Licence (OGL)':'Open Government Licence v3.0',
                    'uk-ogl':'Open Government Licence v3.0',
                    'Open Data Commons Open Database License 1.0':'Open Data Commons Open Database License 1.0',
                    'http://opendatacommons.org/licenses/odbl/1-0/':'Open Data Commons Open Database License 1.0',
                    'http://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/':'Open Government Licence v2.0',
                    'http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/':'Open Government Licence v3.0',
                    }
        if licence_name in known_licences:
            tidied_licence = known_licences[licence_name]
        elif str(licence_name)=="nan":
            tidied_licence = "No licence"
        else:
            tidied_licence = "Custom licence: " + str(licence_name)
        return tidied_licence
    data['License'] = data['License'].apply(tidy_licence)


    return data 

if __name__=="__main__":
    merge_data()
import numpy as np
from collections import defaultdict
from core.nuc_io import open_file

def load_bed_data_track(file_path):

  name = None
  sort_dict = defaultdict(set)
  
  with open_file(file_path, partial=True) as file_obj:
    file_pos = 0
    line = file_obj.readline()
    
    while line.startswith('browser') or line.startswith('track'):
      file_pos = file_obj.tell() # before a non-header line
      line = file_obj.readline()    
    
    while line[0] == '#':
      line = file_obj.readline() 
    
    n_fields = len(line.split())
    have_anno = n_fields > 3
    have_val = n_fields > 4
    have_strand = n_fields > 5
      
  with open_file(file_path) as file_obj:

    for i, line in enumerate(file_obj):
      if line[0] == '#':
        continue
        
      data = line.split()
      chromo = data[0]
      start = int(data[1])
      end = int(data[2])
     
      #if chromo.lower()[:3] == 'chr':
      #  chromo = chromo[3:]
           
      if have_anno:
        label = data[3]
      else:
        label = '%d' % i
      
      if have_val:
        score = float(data[4])
      else:
        score = 1.0
                  
      if have_strand:
        strand = data[5]
        
        if strand == '-':
          if start < end:
            start, end = end, start
 
        elif strand == '+':
          if start > end:
            start, end = end, start
            
      sort_dict[chromo].add(((start, end), score, label))

  region_dict = defaultdict(list)
  value_dict  = defaultdict(list)
  label_dict  = defaultdict(list)
  max_vals = []
  
  for chromo in sort_dict:
    data = sorted(sort_dict[chromo])
    
    regions, scores, labels = zip(*data)
    region_dict[chromo] = np.array(regions)
    value_dict[chromo] = np.array(scores, float)
    label_dict[chromo] = labels
    
    max_vals.append(value_dict[chromo].max())
 
  return region_dict, value_dict, label_dict

  

def save_bed_data_track(file_path, region_dict, value_dict, label_dict=None, scale=1.0):
  
  from nuc_tools import util
  
  #template = 'chr%s\t%d\t%d\t%s\t%.7e\t%s\n' # chr, start, end, label, score, strand
  template = '%s\t%d\t%d\t%s\t%d\t%s\n' # chr, start, end, label, score, strand
  with open(file_path, 'w') as file_obj:
    write = file_obj.write

    for chromo in util.sort_chromosomes(region_dict):
      regions = region_dict[chromo]
      values = value_dict[chromo]
      n = len(regions)
      
      if label_dict:
        labels = label_dict[chromo]
      else:
        labels = ['%d' % i for i in range(n)]
    
      for i, region in enumerate(regions):
        start, end = region
        value = values[i]
        label = labels[i]
 
        if start > end:
          strand = '-'
          start, end = end, start
 
        else:
          strand = '+'
        
        if value < 0:
          value = - value
          strand = '-'
        
        score = value * scale
 
        line = template % (chromo, start, end, label, score, strand)
        
        write(line)

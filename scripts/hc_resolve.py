import os

from math import log, exp

from time import time

import numpy as np

from collections import defaultdict

MIN_SEP = 100
SEP_THRESHOLD = 2e7
SEP_SCALE = 0.5 * SEP_THRESHOLD

def _get_network_score(chr_a, chr_b, pos_a, pos_b, bin_a, bin_b,
                       unambig_bins, chromo_bins, secondary_limit=0.0, primary_limit=3.0):
  
  plim = 10.0 ** primary_limit
  score_l = 1.0
  score_u = 1.0
  unambig_bins_get = unambig_bins.get
  
  a_bins = (bin_a-1, bin_a, bin_a+1)
  b_bins = (bin_b-1, bin_b, bin_b+1)
  
  for a in a_bins:
    rev = a < bin_a
    peri_a = a != bin_a
    
    for b in b_bins:
      key2 = (chr_a, chr_b, a, b)
      
      unambig = unambig_bins_get(key2)
      
      if unambig:
        if rev:
          unambig = unambig[::-1]
        
        if bin_a == a and bin_b == b:
          for pos_1, pos_2 in unambig:
            delta_1 = pos_1-pos_a
            delta_2 = pos_2-pos_b
 
            if delta_1 and delta_2:
              if delta_1 < 0.0:
                delta_1 = max(-delta_1, MIN_SEP)/SEP_SCALE
                score_l += exp(-delta_1*delta_1)
              else:
                delta_1 = max(delta_1, MIN_SEP)/SEP_SCALE
                score_u += exp(-delta_1*delta_1)

              if delta_2 < 0.0:
                delta_2 = max(-delta_2, MIN_SEP)/SEP_SCALE
                score_l += exp(-delta_2*delta_2)
              else:
                delta_2 = max(delta_2, MIN_SEP)/SEP_SCALE
                score_u += exp(-delta_2*delta_2)
             
         
        else:
          for pos_1, pos_2 in unambig:
            delta_1 = pos_1-pos_a
            delta_2 = pos_2-pos_b
 
            if (abs(delta_1) < SEP_THRESHOLD) and (abs(delta_2) < SEP_THRESHOLD):
 
              if delta_1 < 0.0:
                delta_1 = max(-delta_1, MIN_SEP)/SEP_SCALE
                score_l += exp(-delta_1*delta_1)
              else:
                delta_1 = max(delta_1, MIN_SEP)/SEP_SCALE
                score_u += exp(-delta_1*delta_1)

              if delta_2 < 0.0:
                delta_2 = max(-delta_2, MIN_SEP)/SEP_SCALE
                score_l += exp(-delta_2*delta_2)
              else:
                delta_2 = max(delta_2, MIN_SEP)/SEP_SCALE
                score_u += exp(-delta_2*delta_2)
 
            elif peri_a and abs(delta_1) > SEP_THRESHOLD:
              break
        
        if score_l * score_u > plim:
          return primary_limit
        
  if secondary_limit and log(score_l * score_u, 10.0) < secondary_limit: # If not goot enough, check deeper
    intermed_a = defaultdict(list)
    intermed_b = defaultdict(list)
 
    for chr_c, bin_c in chromo_bins:
      append = intermed_a[(chr_c, bin_c)].append
 
      for a in range(bin_a-1, bin_a+2):
        if chr_a > chr_c:
          i, j = 1, 0
          key2 = (chr_c, chr_a, bin_c, a)

        else:
          i, j = 0, 1
          key2 = (chr_a, chr_c, a, bin_c)
 
        for row in unambig_bins_get(key2, []):
          delta = abs(row[i]-pos_a)
 
          if delta and delta < SEP_THRESHOLD:
            append((row[j], row[i]-pos_a))
 
    for chr_c, bin_c in intermed_a:
      append = intermed_b[(chr_c, bin_c)].append
 
      for b in range(bin_b-1, bin_b+2):
        if chr_b > chr_c:
          i, j = 1, 0
          key2 = (chr_c, chr_b, bin_c, b)

        else:
          i, j = 0, 1
          key2 = (chr_b, chr_c, b, bin_c)
 
        for row in unambig_bins_get(key2, []):
          delta = abs(row[i]-pos_b)
 
          if delta and delta < SEP_THRESHOLD:
            append((row[j], row[i]-pos_b))
 
    for key2, values in intermed_b.items():
      for pos_2, delta_2 in values:
        for pos_1, delta_1 in intermed_a[key2]:
          delta_3 = abs(pos_1-pos_2)
 
          if delta_3 and delta_3 < SEP_THRESHOLD:
            for d in (delta_1, delta_2, delta_3):

              if d < 0.0:
                d = max(-d, MIN_SEP)/SEP_SCALE
                score_l += exp(-d*d)
              else:
                d = max(d, MIN_SEP)/SEP_SCALE
                score_u += exp(-d*d)

  return log(score_l * score_u, 10.0)


def _write_ambig_filtered_ncc(in_file_path, out_ncc_path, ag_data, resolved_ag=None, removed_ag=None):
  
  if not resolved_ag:
    resolved_ag = {}
    
  if not removed_ag:
    removed_ag = set()
  
  n = 0
  ambig_group = 0
  seen_res_group = set()
  
  with open(out_ncc_path, 'w') as out_file_obj, open(in_file_path) as in_file_obj:
    write = out_file_obj.write

    for i, line in enumerate(in_file_obj):
      row = line.split()
      chr_a = row[0]
      chr_b = row[6]
      ambig_code = row[12]

      if chr_a > chr_b:
        chr_a, chr_b = chr_b, chr_a

      if '.' in ambig_code: # Updated NCC format
        if int(float(ambig_code)) > 0:
          ambig_group += 1
      else:
        ambig_group = int(ambig_code)    
      
      sz = len(ag_data[ambig_group])
      
      if ambig_group in resolved_ag:    
        keep = 1 if i in resolved_ag[ambig_group] else 0 # Else inactivate
        
        if ambig_group in seen_res_group:
          row[12] = '0.%d' % (keep,)
        else:
          seen_res_group.add(ambig_group)
          row[12] = '%d.%d'  % (sz,keep)
                    
        line = ' '.join(row)+'\n'

      elif ambig_group in removed_ag: # Inactivate
        if ambig_group in seen_res_group:
          row[12] = '0.0'
        else:
          seen_res_group.add(ambig_group)
          row[12] = '%d.0'  % (sz,)
           
        line = ' '.join(row)+'\n'
        
      write(line)    
      
      n += 1

  msg = "Written {:,} of {:,} lines to {}".format(n, i+1, out_ncc_path)
  
  print(msg)
   
      
def _load_bin_sort_ncc(in_ncc_path, sep_threshold=SEP_THRESHOLD):
  
  msg = 'Reading %s' % in_ncc_path
  print(msg)

  ag_data = defaultdict(list)
  nonambig_bins = defaultdict(list)
  ag_positions = defaultdict(set)
  pos_ambig = set()
  
  # Identify positional ambiguity
  
  with open(in_ncc_path) as in_file_obj:
    ambig_group = 0

    for line in in_file_obj:
      chr_a, start_a, end_a, f_start_a, f_end_a, strand_a, chr_b, start_b, end_b, \
        f_start_b, f_end_b, strand_b, ambig_code, pair_id, swap_pair = line.split()
        
      if '.' in ambig_code: # Updated NCC format
        if int(float(ambig_code)) > 0:
          ambig_group += 1 # Count even if inactive; keep consistent group numbering

      else:
        ambig_group = int(ambig_code)          

      if ambig_code.endswith('.0'): # Inactive
        continue
      
      if strand_a == '+':
        pos_a = int(f_end_a)
      else:
        pos_a = int(f_start_a)

      if strand_b == '+':
        pos_b = int(f_end_b)
      else:
        pos_b = int(f_start_b)
      
      ag_positions[ambig_group].add((chr_a, pos_a))
      ag_positions[ambig_group].add((chr_b, pos_b))
  
  n_pos_ag = 0
  for ag in ag_positions:
    chr_pos = ag_positions[ag]
    
    if len(chr_pos) > 4:
      pos_ambig.add(ag)
      
    else:
      chr_roots = set([x[0].split('.')[0] for x in chr_pos])
      
      if len(chr_roots) > 2:
        pos_ambig.add(ag)
  
  msg = 'Found {:,} positional ambiguity groups from {:,} '.format(len(pos_ambig), ambig_group)
  print(msg)
    
  # Bin and group
  ambig_bins = defaultdict(list)
  
  with open(in_ncc_path) as in_file_obj:
    ambig_group = 0

    for i, line in enumerate(in_file_obj):
      chr_a, start_a, end_a, f_start_a, f_end_a, strand_a, chr_b, start_b, end_b, \
        f_start_b, f_end_b, strand_b, ambig_code, pair_id, swap_pair = line.split()

      if '.' in ambig_code: # Updated NCC format
        if int(float(ambig_code)) > 0:
          ambig_group += 1
      else:
        ambig_group = int(ambig_code)          

      if ambig_code.endswith('.0'): # Inactive
        continue
      
      if strand_a == '+':
        pos_a = int(f_end_a)
      else:
        pos_a = int(f_start_a)

      if strand_b == '+':
        pos_b = int(f_end_b)
      else:
        pos_b = int(f_start_b)
 
      if chr_a > chr_b:
        chr_a, chr_b = chr_b, chr_a
        pos_a, pos_b = pos_b, pos_a
      
      bin_a = int(pos_a/sep_threshold)
      bin_b = int(pos_b/sep_threshold)
 
      key = (chr_a, chr_b, bin_a, bin_b)
      ag_data[ambig_group].append((key, pos_a, pos_b, i))
      
      
      if ambig_group in pos_ambig: 
        ambig_bins[key].append((pos_a, pos_b, ambig_group))
      else:
        nonambig_bins[key].append((pos_a, pos_b, ambig_group))
      
      
      
  msg = 'Loaded {:,} contact pairs in {:,} ambiguity groups'.format(i+1, len(ag_data))
  print(msg)
 
  msg = ' .. sorting data'
  print(msg)

  unambig_bins = {}
  chromo_pair_counts = defaultdict(int)
  chromo_bins = set()

  for key in nonambig_bins:
    chr_a, chr_b, bin_a, bin_b = key
    vals = sorted(nonambig_bins[key]) # Sort by 1st chromo pos
    unambig = [x[:2] for x in vals if len(ag_data[x[2]]) == 1]
 
    unambig_bins[key] = unambig
    nonambig_bins[key] = vals
             
    if unambig:
      chromo_bins.add((chr_a, bin_a))
      chromo_bins.add((chr_b, bin_b))
      
      chromo_pair_counts[(chr_a, chr_b)] += len(unambig)
      
  msg = ' .. done'
  print(msg)
 
  return ag_data, pos_ambig, chromo_bins, nonambig_bins, unambig_bins, ambig_bins, dict(chromo_pair_counts)


def remove_isolated_unambig(in_ncc_path, out_ncc_path, threshold=0.01, sep_threshold=SEP_THRESHOLD, homo_trans_dens_quant=90.0):
  
  ag_data, pos_ambig, chromo_bins, nonambig_bins, unambig_bins, ambig_bins, chromo_pair_counts = _load_bin_sort_ncc(in_ncc_path)
 
  msg_template = ' .. Processed:{:>7,} Removed:{:>7,}'
  
  all_bins = {}
  for key in set(ambig_bins) | set(nonambig_bins):
    all_bins[key] = ambig_bins.get(key, []) + nonambig_bins.get(key, [])
  
  removed_ag = set()
  resolved_ag = {}
  
  msg = 'Removing unambiguous inter-homologue contacts from anomolously dense regions'
  print(msg)
  
  bin_counts = {}
  for key in all_bins:
    chr_a, chr_b, bin_a, bin_b = key
    root_a = chr_a.split('.')[0]
    root_b = chr_b.split('.')[0]
    
    if root_a == root_b:
      n_contacts = len(all_bins[key])
      
      if n_contacts:
        bin_counts[key] = n_contacts
  
  counts = list(bin_counts.values())
  upper_dens_thresh = np.percentile(counts, homo_trans_dens_quant)
  
  """
  print('Quantiles', np.log10(np.percentile(counts, [1,5,10,50,80])))
  print('Quantiles', np.percentile(counts, [1,5,10,50,80]))
  from matplotlib import pyplot as plt
  plt.hist(np.log10(counts), bins=100)
  plt.show()     
  """
  
  for ag in ag_data:
    pairs = ag_data[ag]
    n_pairs = len(pairs)
    keep = []
    
    for key, pos_a, pos_b, line_idx in pairs:
      chr_a, chr_b, bin_a, bin_b = key
 
      if (chr_a != chr_b) and (key in bin_counts): # Homolog trans only
        count = bin_counts[key]
        
        if count < upper_dens_thresh:
          for a in range(bin_a-1, bin_a+2):
            for b in range(bin_b-1, bin_b+2):
              if a == bin_a and b == bin_b:
                continue
 
              key2 =  (chr_a, chr_b, a, b)
 
              for pos1, pos2, ag1 in all_bins.get(key2, []):
                if (abs(pos1-pos_a) < sep_threshold) and (abs(pos2-pos_b) < sep_threshold):
                  count += 1
 
                  if count > upper_dens_thresh:
                    break
              
              else:
                continue
              break
            
            else:
              continue
            break  
              
        if count < upper_dens_thresh:
          keep.append(line_idx)
        
        elif (n_pairs == 1) and (key in unambig_bins):
          
          contacts = []
          for pos1, pos2 in unambig_bins[key]:
            if (pos1 != pos_a) or (pos2 != pos_b):
              contacts.append((pos1, pos1))
          
          unambig_bins[key] = contacts
          
      else:
        keep.append(line_idx)
        
    if keep:
      if len(keep) < n_pairs:
        resolved_ag[ag] = keep        
    
    else:      
      removed_ag.add(ag)
    
  msg = ' .. removed {:,}'.format(len(removed_ag))
  print(msg)
 
  msg = ' .. partly resolved {:,}'.format(len(resolved_ag))
  print(msg)

  scores = []
  it = 0

  unambig_pairs = [(g, ag_data[g][0]) for g in ag_data if len(ag_data[g]) == 1 and (g not in removed_ag)] #  and (g not in resolved_ag)]
 
  msg = 'Scoring {:,} unambiguous pairs'.format(len(unambig_pairs))
  print(msg)
  
  for ag, (key, pos_a, pos_b, line_idx) in unambig_pairs:

    it += 1
    if it % 1000 == 0:
      msg = msg_template.format(it, len(removed_ag))
      print(msg)
 
    group_score = 0.0 
    chr_a, chr_b, bin_a, bin_b = key

    if key not in unambig_bins:
      print(key, ag, ag in removed_ag, ag in resolved_ag, len(ag_data[ag]))
      
    contacts = unambig_bins[key]
 
    if contacts:
      score = _get_network_score(chr_a, chr_b, pos_a, pos_b, bin_a, bin_b, unambig_bins, chromo_bins, secondary_limit=threshold) 
    else:
      score = 0.0

    if score < threshold:
      removed_ag.add(ag)
  
  
  _write_ambig_filtered_ncc(in_ncc_path, out_ncc_path, ag_data, resolved_ag=resolved_ag, removed_ag=removed_ag)

  msg = msg_template.format(it, len(removed_ag))     
  print(msg)


def resolve_contacts(in_ncc_path, out_ncc_path, remove_isolated=False,
                     score_threshold=2.0, min_trans_relay=5, remove_pos_ambig=False):

  msg_template = ' .. Processed:{:>7,} Resolved:{:>7,} Time taken:{:.3f} s'

  msg = 'Reading contact data'
  print(msg)
  
  resolved_ag = {}
  removed_ag = set()
  n_pos_ambig = 0
  
  ag_data, pos_ambig, chromo_bins, nonambig_bins, unambig_bins, ambig_bins, chromo_pair_counts = _load_bin_sort_ncc(in_ncc_path)

  roots = set()
  chromos = set()
  for chr_a, chr_b in chromo_pair_counts:
    roots.add(chr_a.split('.')[0])
    roots.add(chr_b.split('.')[0])
    chromos.add(chr_a)
    chromos.add(chr_b)
  
  chromos = list(chromos)  
  trans_close = {} 
  
  for i, chr_a in enumerate(chromos[:-1]):
    for chr_b in chromos[i:]:
      n_inter = chromo_pair_counts.get((chr_a, chr_b), 0)
 
      for chr_c in chromos:
        if chr_c in (chr_a, chr_b):
          continue
 
        a = chromo_pair_counts.get((chr_a, chr_c), 0)
        b = chromo_pair_counts.get((chr_b, chr_c), 0)
        c = chromo_pair_counts.get((chr_c, chr_a), 0)
        d = chromo_pair_counts.get((chr_c, chr_b), 0)
 
        n_inter += np.sqrt((a + c) * (b + d))
 
      trans_close[(chr_a, chr_b)] = n_inter
      trans_close[(chr_b, chr_a)] = n_inter
  
  #from matplotlib import pyplot as plt
  #vals = sorted(trans_close.values())
  #plt.hist(vals, bins=50, range=(0,50))
  #plt.show()     

  msg = 'Filtering with network scores'
  print(msg)
  
  scores = [[], [], [], []]
  it = 0  
  t0 = time()
    
  for ag in ag_data:
    it += 1
    if it % 10000 == 0:
      t1 = time()
      msg = msg_template.format(it, len(resolved_ag), t1-t0)
      t0 = t1
      print(msg)
    
    if ag in removed_ag:
      continue
    
    pairs = ag_data[ag]
 
    if len(pairs) == 1:
      continue
      
    if len(pairs) > 16:
      removed_ag.add(ag)
      continue

    poss_pairs = []
    for key, pos_a, pos_b, line_idx in pairs:
      chr_pair = tuple(key[:2])
      
      if (chr_pair not in trans_close) or (trans_close[chr_pair] >= min_trans_relay): 
        poss_pairs.append((key, pos_a, pos_b, line_idx))
    
    if poss_pairs and len(poss_pairs) < len(pairs): # A chromo pair can be excluded
      if len(poss_pairs) == 1: # Only one sensible trans possibility
         key, pos_a, pos_b, line_idx = poss_pairs[0]
         chr_a, chr_b, bin_a, bin_b = key
         
         if nonambig_bins.get(key) and _get_network_score(chr_a, chr_b, pos_a, pos_b, bin_a, bin_b, unambig_bins, chromo_bins):
           resolved_ag[ag] = (line_idx,)
         else:
           removed_ag.add(ag)
        
         continue
      
      else:
        resolved_ag[ag] = tuple([x[3] for x in poss_pairs]) # Might be refined further

    line_indices = []
    group_scores = [0.0] * 16
    
    for p, (key, pos_a, pos_b, line_idx) in enumerate(pairs):
      line_indices.append(line_idx)
      chr_a, chr_b, bin_a, bin_b = key
      contacts = nonambig_bins.get(key)
 
      if contacts:
        score = _get_network_score(chr_a, chr_b, pos_a, pos_b, bin_a, bin_b, unambig_bins, chromo_bins)
 
      else:
        score = 0.0
            
      group_scores[p] = score

    a, b, c, *d = np.argsort(group_scores)[::-1]
          
    if group_scores[a]  >  score_threshold * group_scores[b]:
      resolved_ag[ag] = (line_indices[a],)
      
    elif group_scores[b]  >  score_threshold * group_scores[c]: # First two were close
      resolved_ag[ag] = (line_indices[a], line_indices[b])
      
    elif group_scores[a] == 0.0: # Best is isolated
      if remove_isolated:
        removed_ag.add(ag)

  if remove_pos_ambig: 
    removed_ag.update(pos_ambig)
  
  _write_ambig_filtered_ncc(in_ncc_path, out_ncc_path, ag_data, resolved_ag, removed_ag)
  
  msg = msg_template.format(it, len(resolved_ag), n_pos_ambig)
  print(msg)  


if __name__ == '__main__': 
  
  
  # All functions take an NCC file and create a filtered NCC file
  
  # Cleanup ambig so noise doesn't affect disambiguation too much
  import sys
  sys.path.append('/home/tjs23/gh/nuc_tools/')
  
  from tools.contact_map import contact_map
    
  #ncc_file_path = '/data/hi-c/hybrid/fastq/SRR5229047_r1_r2_1CDS1-153.ncc'
  ncc_file_path = '/data/hi-c/hybrid/fastq/SRR5229055_r1_r2_1CDS2-145.ncc'
  
  file_root = os.path.splitext(ncc_file_path)[0]
  
  clean_ncc_path   = file_root + '_clean.ncc'
  filter1_ncc_path = file_root + '_filter1.ncc'
  filter2_ncc_path = file_root + '_filter2.ncc'
  filter3_ncc_path = file_root + '_resolved.ncc'
 
  clean_pdf   = file_root + '_clean.pdf'
  filter1_pdf = file_root + '_filter1.pdf'
  filter2_pdf = file_root + '_filter2.pdf'
  filter3_pdf = file_root + '_resolved.pdf'
  
  
  remove_isolated_unambig(ncc_file_path, clean_ncc_path) 
  
  contact_map([clean_ncc_path], clean_pdf, bin_size=None,
               no_separate_cis=True, is_single_cell=True)
  
  # The contact resolution iterative process 
 
  # Permissive
  resolve_contacts(clean_ncc_path, filter1_ncc_path, score_threshold=5.0)

  contact_map([filter1_ncc_path], filter1_pdf, bin_size=None,
               no_separate_cis=True, is_single_cell=True)
  
  # More strict
  resolve_contacts(filter1_ncc_path, filter2_ncc_path)
  
  contact_map([filter2_ncc_path], filter2_pdf, bin_size=None,
              no_separate_cis=True, is_single_cell=True)
  
  # Strict again and remove isolated ambigous
  resolve_contacts(filter2_ncc_path, filter3_ncc_path, remove_isolated=True)
 
  contact_map([filter3_ncc_path], filter3_pdf, bin_size=None, bin_size2=250.0,
               no_separate_cis=True, is_single_cell=True)
  
# To do 
# test with nuc3d 


 
"""
all ncc files (more than 40) for Nagano dip3 is on /mnt/delphi/scratch/shared/dip_ncc/dip_3

and also the report and pdf contact maps.

Sorry those perhaps include few ones that do not give good structures. If you want to know which one gives a structure, all 400k structures
are inside /mnt/delphi/scratch/shared/Nagano_serumLif/dip_3


The naming is very weird: the ones after filtering/disambiguation is called ...._filtered_isoRm_hc_remove_more.ncc sorry for a very long name
that only makes sense to me... because this indicates the version of code I'm using...

Another note: all original ncc files are in new format , i.e. the 1.1,1.2 etc column, while _filtered_isoRm_hc_remove_more.ncc files are in
old format: I copied the 14th column to the 13th column (13th and 14th are the same), there is no 1.1 like columns. That's due to historical
reasons. I coded the code in the way that it works with the old format initially. By the time Wayne was testing the new version of
nuc_dynamics, sometimes it still have problem with new format.  So I thought it was all safer to keep the old format as output (it takes new
format as input fine).

I've attached the code here for disambiguation. The way to run it is python3 hc_resolve_v3_old_hyb.py ncc_file_input 15

(set 15 for Nagano's and our new hyb, and 25 for our old hyb)(normally it's all 15, except our weird old line which has very very few unambig
contacts).

it will output some other intermediate files... delete all of them, no use.... it will also print out tons of numbers on screen, again,
ignore all of them. Those are only for some checking, would be useful in extreme cases to identify possible problems. I will make it nicer
for users once for publication...

At /mnt/delphi/wb104/nuc_dynamics2_runs/diploid_3. And /mnt/delphi \u2014> /home if you are looking on delphi itself rather than demeter
(etc.).

> On 17 Nov 2020, at 14:52, X. Ma <xm227@cam.ac.uk> wrote: > > For structurally disambiguated final ncc files, they are all inside Wayne's
folder delphi/wb104/nuc_dynamics2_runs/dip3 or dip_3--find the 400k final ncc.

delphi:/home/scratch/shared/dip_ncc/dip_3/

Processed data at:

munro-i7:/data/hi-c/hybrid/fastq

"""      
      
      
      
      
      
      
      
      

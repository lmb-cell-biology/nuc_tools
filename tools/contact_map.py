import datetime
import numpy as np
import os, sys

from math import ceil
from collections import defaultdict
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.ticker import LogFormatter 
from matplotlib.backends.backend_pdf import PdfPages

PROG_NAME = 'contact_map'
VERSION = '1.0.0'
DESCRIPTION = 'Chromatin contact (NCC format) Hi-C contact map PDF display module'
DEFAULT_CIS_BIN_KB = 250
DEFAULT_TRANS_BIN_KB = 500
DEFAULT_MAIN_BIN_KB = 1000

def _downsample_matrix(in_array, new_shape):
    
    p, q = in_array.shape
    n, m = new_shape
    
    if p % n == 0:
      pad_a = 0
    else:
      pad_a = n * int(1+p//n) - p

    if q % m == 0:
      pad_b = 0
    else:
      pad_b = m * int(1+q//m) - q 
    
    if pad_a or pad_b:
      in_array = np.pad(in_array, [(0,pad_a), (0,pad_b)], 'constant')
      p, q = in_array.shape
        
    shape = (n, p // n,
             m, q // m)
    
    return in_array.reshape(shape).sum(-1).sum(1)


def _get_chromo_offsets(bin_size, chromos, chromo_limits):
  
  chromo_offsets = {}
  label_pos = []
  n = 0
  for chromo in chromos: # In display order
    s, e = chromo_limits[chromo]
    c_bins = int(ceil(e/float(bin_size))) - int(s/bin_size)
    chromo_offsets[chromo] = s, n, c_bins # Start bp, start bin index, num_bins
    label_pos.append(n + c_bins/2)
    n += c_bins
    n += 1 # Add space between chromos on matrix
  
  return n, chromo_offsets, label_pos
  

def get_contact_arrays_matrix(contacts, bin_size, chromos, chromo_limits):
 
  n, chromo_offsets, label_pos = _get_chromo_offsets(bin_size, chromos, chromo_limits)
  
  matrix = np.zeros((n, n, 2), float)
     
  n_ambig = 0
  n_homolog = 0
  n_trans = 0
  n_cis = 0
  n_cont = 0
  
  for i, chr_1 in enumerate(chromos):
    for chr_2 in chromos[i:]:

      if chr_1 > chr_2:
        chr_a, chr_b = chr_2, chr_1
      else:
        chr_a, chr_b = chr_1, chr_2

      contact_matrix = contacts.get((chr_a, chr_b))

      if contact_matrix is None:
        continue
        
      count = int(contact_matrix.sum())
      
      bp_a, bin_a, size_a = chromo_offsets[chr_a]
      bp_b, bin_b, size_b = chromo_offsets[chr_b]

      sub_mat = _downsample_matrix(contact_matrix, (size_a, size_b))
      
      matrix[bin_a:bin_a+size_a,bin_b:bin_b+size_b,0] += sub_mat
      
      matrix[bin_b:bin_b+size_b,bin_a:bin_a+size_a,0] += sub_mat.T
      
      if chr_a != chr_b:
        if ('.' in chr_a) and ('.' in chr_b) and (chr_a.split('.')[0] == chr_b.split('.')[0]):
          n_homolog += count

        n_trans += count

      else:
        n_cis += count
      
      n_cont += count 
  
  return (n_cont, n_cis, n_trans, n_homolog, n_ambig), matrix, label_pos


def _limits_to_shape(limits_a, limits_b, bin_size):
  
  start_a, end_a = limits_a
  start_b, end_b = limits_b
  
  n = int(ceil(end_a/float(bin_size))) - int(start_a/bin_size)
  m = int(ceil(end_b/float(bin_size))) - int(start_b/bin_size)
  
  return n, n


def get_single_array_matrix(contact_matrix, limits_a, limits_b, is_cis, orig_bin_size, bin_size):

  
  if bin_size == orig_bin_size:
    if is_cis:
      a, b = contact_matrix.shape
      n = max(a, b)
      matrix = np.zeros((n,n), float)
      matrix[:a,:b] += contact_matrix
      matrix[:b,:a] += contact_matrix.T
 
    else:
      matrix = contact_matrix.astype(float)
  
  else:
    n, m = _limits_to_shape(limits_a, limits_b, bin_size)
    matrix = _downsample_matrix(contact_matrix, (n, m)).astype(float)
     
    if is_cis:
      matrix += matrix.T
  
  return matrix
  

def get_single_list_matrix(contact_list, limits_a, limits_b, bin_size):
  
  n, m = _limits_to_shape(limits_a, limits_b, bin_size)

  matrix = np.zeros((n, m), float)
  
  for p_a, p_b, ag in contact_list:
    a = int((p_a-start_a)/bin_size)
    b = int((p_b-start_b)/bin_size) 

    matrix[a, b] += 1.0
    matrix[b, a] += 1.0
 
  return matrix
  
  
def get_contact_lists_matrix(contacts, bin_size, chromos, chromo_limits):
  
  n, chromo_offsets, label_pos, chromo_spans = _get_chromo_offsets(bin_size, chromos, chromo_limits)
  
  # Fill contact map matrix, last dim is for (un)ambigous
  matrix = np.zeros((n, n, 2), float)
  
  groups = defaultdict(int)
  for key in contacts:
    for p_a, p_b, ag in contacts[key]:
      groups[ag] += 1

  homolog_groups = set()
  trans_groups = set()
  cis_groups = set()
  
  for i, chr_1 in enumerate(chromos):
    for chr_2 in chromos[i:]:

      if chr_1 > chr_2:
        chr_a, chr_b = chr_2, chr_1
      else:
        chr_a, chr_b = chr_1, chr_2

      contact_list = contacts.get((chr_a, chr_b))

      if contact_list is None: # Nothing for this pair: common for single-cell Hi-C
        continue

      s_a, off_a, size_a = chromo_offsets[chr_a]
      s_b, off_b, size_b = chromo_offsets[chr_b]

      for p_a, p_b, ag in contact_list:
        if chr_a != chr_b:
          if ('.' in chr_a) and ('.' in chr_b) and (chr_a.split('.')[0] == chr_b.split('.')[0]):
            homolog_groups.add(ag)

          else:
            trans_groups.add(ag)

        else:
          cis_groups.add(ag)

        a = off_a + int((p_a-s_a)/bin_size)
        b = off_b + int((p_b-s_b)/bin_size)
 
        k = 0 if groups[ag] == 1 else 1

        matrix[a, b, k] += 1.0
        matrix[b, a, k] += 1.0

  n_ambig = len([x for x in groups.values() if x > 1])
  n_homolog = len(homolog_groups)
  n_trans = len(trans_groups)
  n_cis = len(cis_groups)
  n_cont = len(groups)

  return (n_cont, n_cis, n_trans, n_homolog, n_ambig), matrix, label_pos
  
                
def contact_map(in_path, out_path, bin_size=None, bin_size2=250.0, bin_size3=500.0,
                separate_cis=False, separate_trans=False, show_chromos=None, screen_gfx=False,
                black_bg=False, font=None, font_size=12, line_width=0.2, min_contig_size=None):
  
  from nuc_tools import io, util
  from formats import ncc, npz
  
  if out_path:
    file_root, file_ext = os.path.splitext(out_path)
    file_ext = file_ext.lower()
    
    if file_ext == '.pdf':
      out_path = file_root + '.pdf'
    
  else:
    file_root, file_ext = os.path.splitext(in_path)
    out_path = file_root + '.pdf'
  
  if screen_gfx:
    util.info('Displaying contact map for {}'.format(in_path))
  else:
    util.info('Making PDF contact map for {}'.format(in_path))
  
  if in_path.lower().endswith('.ncc'):
    file_bin_size = None
    chromosomes, chromo_limits, contacts = ncc.load_ncc(in_path)
    
  else:
    file_bin_size, chromo_limits, contacts = npz.load_npz_contacts(in_path)

  if not chromo_limits:
    util.critical('No chromosome contact data read')

  if min_contig_size:
    min_contig_size = int(min_contig_size * 1e6)
  else:
    largest = max([e-s for s, e in chromo_limits.values()])
    min_contig_size = int(0.05*largest) 
    util.info('Min. contig size not specified, using 5% of largest: {:,} bp'.format(min_contig_size))
  
  if show_chromos:
    chr_names = ', '.join(sorted(chromo_limits))
    
    filtered = {}
    for chromo, lims in chromo_limits.items():
       if chromo in show_chromos:
         filtered[chromo] = lims
       
       elif chromo.lower().startswith('chr') and (chromo[3:] in show_chromos):
         filtered[chromo] = lims
         
    chromo_limits = filtered
  
    if not chromo_limits:
      util.critical('Chromosome selection doesn\'t match any in the contact file. Available: {}'.format(chr_names))
  
  if bin_size:
    bin_size = int(bin_size * 1e3)
     
  else:
    tot_size = 0
    
    for chromo in chromo_limits:
      s, e = chromo_limits[chromo]
      size = e-s
      
      if size >= min_contig_size:
        tot_size += size 
    
    bin_size = int(tot_size/1000)
    util.info('Bin size not specified, using approx. 1000 x 1000 bin equivalent: {:,} bp'.format(bin_size))
    
  bin_size2 = int(bin_size2 * 1e3)
  bin_size3 = int(bin_size3 * 1e3)
          
  # Get sorted chromosomes, ignore small contigs as appropriate
  chromos = []
  skipped = []
  for chromo in chromo_limits:
    s, e = chromo_limits[chromo]

    if (e-s) < min_contig_size:
      if show_chromos and (chromo in show_chromos):
        msg = 'Chromosome {} is below the size limit but was nonethless included as it was included in the -chr option'
        util.info(msg.format(chromo))        
      else:
        skipped.append(chromo)
        continue
        
    if chromo.lower().startswith('chr'):
      c = chromo[3:]
    else:
      c = chromo

    if c.split('.')[-1].upper() in ('A','B'):
      try:
        key = ('%09d' % int(c.split('.')[0]), c.split('.')[-1])
      except ValueError as err:
        key = (c, c.split('.')[-1],)

    else:
      try:
        key = '%09d' % int(c)
      except ValueError as err:
        key = c

    chromos.append((key, chromo))

  if skipped:
    util.info('Skipped {:,} small chromosomes/contigs < {:,} bp'.format(len(skipped), min_contig_size))

  chromos.sort()
  chromos = [x[1] for x in chromos]
   
  chromo_labels = []
  for chromo in chromos:
    if chromo.upper().startswith('CHR'):
      chromo = chromo[3:]
    chromo_labels.append(chromo)

  if file_bin_size:
    count_list, full_matrix, label_pos = get_contact_arrays_matrix(contacts, bin_size, chromos, chromo_limits)
    n_cont, n_cis, n_trans, n_homolog, n_ambig = count_list
    
  else:
    count_list, full_matrix, label_pos = get_contact_lists_matrix(contacts, bin_size, chromos, chromo_limits)
    n_cont, n_cis, n_trans, n_homolog, n_ambig = count_list

  n = len(full_matrix)
  util.info('Full contact map size %d x %d' % (n, n))
  
  f_cis = 100.0 * n_cis / float(n_cont or 1)
  f_trans = 100.0 * n_trans / float(n_cont or 1)
  
  if n_homolog:
    f_homolog = 100.0 * n_homolog / float(n_cont or 1)  
    stats_text1 = 'Contacts:{:,d} cis:{:,d} ({:.1f}%) trans:{:,d} ({:.1f}%) homolog:{:,d} ({:.1f}%)'
    stats_text1 = stats_text1.format(n_cont, n_cis, f_cis, n_trans, f_trans, n_homolog, f_homolog)
  
  else:
    stats_text1 = 'Contacts:{:,d} cis:{:,d} ({:.1f}%) trans:{:,d} ({:.1f}%)'
    stats_text1 = stats_text1.format(n_cont, n_cis, f_cis, n_trans, f_trans)
  
  if black_bg:
    cmap = LinearSegmentedColormap.from_list(name='B', colors=['#000000', '#BB0000', '#DD8000', '#FFFF00', '#FFFF80','#FFFFFF'], N=255)    
    cmap.set_bad(color='#404040')
  else:
    cmap = LinearSegmentedColormap.from_list(name='W', colors=['#FFFFFF', '#0080FF' ,'#FF0000','#000000'], N=255)
    cmap.set_bad(color='#B0B0B0')
 
  fig, ax = plt.subplots()
  
  cax = ax.matshow(full_matrix[:,:,0], interpolation=None, norm=LogNorm(vmin=1), cmap=cmap, origin='upper')
  
  ax.xaxis.set_ticks(label_pos)
  ax.yaxis.set_ticks(label_pos)
  ax.set_xticklabels(chromo_labels)
  ax.set_yticklabels(chromo_labels)
  ax.xaxis.tick_bottom()
  ax.xaxis.set_tick_params(direction='out')
  ax.yaxis.set_tick_params(direction='out')
  ax.set_title(os.path.basename(in_path))
  ax.text(0, -int(1 + 0.01 * n), stats_text1, fontsize=11)  
  ax.set_xlabel('Chromosome')
  ax.set_ylabel('Chromosome')
  cbar = plt.colorbar(cax)
  cbar.set_label('Count (%.2f Mb bins)' % (bin_size/1e6), fontsize=11)
  
  if screen_gfx:
    pdf = None
    plt.show()
  else:
    pdf = PdfPages(out_path)   
    pdf.savefig()
  
  plt.close()
  
  formatter = LogFormatter(10, labelOnlyBase=False) 
  
  if separate_cis or separate_trans:
  
    for i, chr_a in enumerate(chromos):
      for chr_b in chromos[i:]:
        
        is_cis = chr_a == chr_b
        
        if is_cis and not separate_cis:
          continue
          
        elif (not is_cis) and not separate_trans:
          continue
          
        pair = tuple(sorted([chr_a, chr_b]))
        limits_a = chromo_limits[pair[0]]
        limits_b = chromo_limits[pair[1]]
        
        pair_bin_size = bin_size2 if is_cis else bin_size3
                
        if file_bin_size:
          matrix = get_single_array_matrix(contacts[pair], limits_a, limits_b, is_cis, file_bin_size, pair_bin_size)
        else:
          matrix = get_single_list_matrix(contacts[pair], limits_a, limits_b, pair_bin_size)
        
        a, b = matrix.shape
        fa = int(limits_a[0]/pair_bin_size)
        fb = int(limits_b[0]/pair_bin_size)
        
        # Could consider not showing blank segments
        
        xp_max = 10 ** int(ceil(np.log10(a)))  
        xlabel_pos = np.arange(0, a, xp_max/10.0) # Pixels/bins
        xlabels = ['%.1f' % (x*pair_bin_size/1e6) for x in xlabel_pos]
 
        yp_max = 10 ** int(ceil(np.log10(b)))  
        ylabel_pos = np.arange(0, b, yp_max/10.0) # Pixels/bins
        ylabels = ['%.1f' % (y*pair_bin_size/1e6) for y in ylabel_pos]

        fig, ax = plt.subplots()
 
        cax = ax.matshow(matrix, interpolation=None, cmap=cmap, norm=LogNorm(vmin=1), origin='upper')
        ax.xaxis.tick_bottom()
        ax.set_xticklabels(xlabels, fontsize=9)
        ax.set_yticklabels(ylabels, fontsize=9)               
        ax.xaxis.set_ticks(xlabel_pos)
        ax.yaxis.set_ticks(ylabel_pos)
        ax.xaxis.set_tick_params(direction='out')
        ax.yaxis.set_tick_params(direction='out')
        ax.set_xlabel('Position %s (Mb)' % pair[0])
        ax.set_ylabel('Position %s (Mb)' % pair[1])
        
        title = 'Chromosome %s' % chr_a if is_cis else 'Chromosomes %s - %s ' % pair
          
        ax.set_title(title)
        util.info('Making map for ' + title)
        
        cbar = plt.colorbar(cax) if matrix.max() > 10 else plt.colorbar(cax, ticks=list(range(10)), format=formatter)
          
        if is_cis:  
          cbar.set_label('Count (%.1f kb bins)' % (pair_bin_size/1e3), fontsize=11)
        else:
          cbar.set_label('Count (%.3f Mb bins)' % (pair_bin_size/1e6), fontsize=11)
 
        if pdf:
          pdf.savefig()
        else:
          plt.show()
          
        plt.close()
  
  if pdf:
    pdf.close()
    util.info('Written {}'.format(out_path))

def main(argv=None):

  from argparse import ArgumentParser
  from nuc_tools import util, io
  
  if argv is None:
    argv = sys.argv[1:]

  epilog = 'For further help email tjs23@cam.ac.uk or wb104@cam.ac.uk'

  arg_parse = ArgumentParser(prog=PROG_NAME, description=DESCRIPTION,
                             epilog=epilog, prefix_chars='-', add_help=True)

  arg_parse.add_argument(metavar='CONTACT_FILE', nargs='+', dest='i',
                         help='Input NCC format (single-cell) or NPZ (binned, bulk Hi-C data) chromatin contact file(s). Wildcards accepted')

  arg_parse.add_argument('-o', metavar='OUT_FILE', nargs='+', default=None,
                         help='Optional output file name. If not specified, a default based on the input file name and output format will be used. ' \
                              'If multiple input contact files are specified there must be one output for each input')
  
  arg_parse.add_argument('-chr', metavar='CHROMOSOMES', nargs='+', default=None,
                         help='Optional selection of chromsome names to generate contact maps for.')

  arg_parse.add_argument('-c', default=False, action='store_true',
                         help='Display separate contact maps for all chromosomes (intra-chromosomal contacts). ' \
                              'By default only the overall whole-genome map is displayed')

  arg_parse.add_argument('-t', default=False, action='store_true',
                         help='Display separate contact maps for all trans (inter-chromosomal) pairs. ' \
                              'By default only the overall whole-genome map is displayed')

  arg_parse.add_argument('-g', default=False, action='store_true',
                         help='Display graphics on-screen using matplotlib, where possible and do not automatically save output.')

  arg_parse.add_argument('-s1', default=DEFAULT_MAIN_BIN_KB, metavar='BIN_SIZE', type=float,
                         help='Binned sequence region size (the resolution) for the overall contact map, in kilobases. Default is {:.1f} kb'.format(DEFAULT_MAIN_BIN_KB))

  arg_parse.add_argument('-s2', default=DEFAULT_CIS_BIN_KB, metavar='BIN_SIZE', type=float,
                         help='Binned sequence region size (the resolution) for separate intra-chromsomal maps, ' \
                              'in kilobases. Default is {:.1f} kb'.format(DEFAULT_CIS_BIN_KB))
  
  arg_parse.add_argument('-s3', default=DEFAULT_TRANS_BIN_KB, metavar='BIN_SIZE', type=float,
                         help='Binned sequence region size (the resolution) for separate inter-chromsomal maps, ' \
                              'in kilobases. Default is {:.1f} kb'.format(DEFAULT_TRANS_BIN_KB))

  arg_parse.add_argument('-m', default=0.0, metavar='MIN_CONTIG_SIZE', type=float,
                         help='The minimum chromosome/contig sequence length in Megabases for inclusion. Default is 10% of the largest chromosome/contig length.')

  arg_parse.add_argument('-b', default=False, action='store_true',
                         help='Specifies that the contact map should have a white background (default is white)')
                         
  args = vars(arg_parse.parse_args(argv))

  in_paths = args['i']
  out_paths = args['o']
  screen_gfx = args['g']
  bin_size = args['s1']
  bin_size2 = args['s2']
  bin_size3 = args['s3']
  min_contig_size = args['m']
  black_bg = args['b']
  sep_cis = args['c']
  sep_trans = args['t']
  chromos = args['chr']
  
  if not in_paths:
    arg_parse.print_help()
    sys.exit(1)
  
  if out_paths:
    if len(out_paths) != len(in_paths):
      util.critical('The number of output file paths does not match the number input')
      
    if screen_gfx:
      util.warn('Output files will not be written in screen graphics (-g) mode')
      out_paths = [None] * len(in_paths)
      
  else:
    out_paths = [None] * len(in_paths)

  for in_path, out_path in zip(in_paths, out_paths):
    if not os.path.exists(in_path):
      util.critical('Input contact file could not be found at "{}"'.format(in_path))

    contact_map(in_path, out_path, bin_size, bin_size2, bin_size3,
                sep_cis, sep_trans, chromos, screen_gfx,
                black_bg, min_contig_size=min_contig_size)


if __name__ == "__main__":
  sys.path.append(os.path.dirname(os.path.dirname(__file__)))
  main()

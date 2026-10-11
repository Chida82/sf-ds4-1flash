#!/usr/bin/perl
# Every DS4_* name the sources read has a line in ds4_env.def, and every line
# names something the sources still read. `make env-check`, first step of
# `make test`; usage: env_check.pl ds4_env.def SOURCE...
#
# A name is a whole string literal "DS4_...". Literals that are not variables
# this build reads are left out:
# - a DS4_ROCM_* name passed first to glm_graph_env_present/value: the helper
#   discards it and reads only the Metal name after it;
# - DS4_IMAGE_, the prefix of the server's image marker text;
# - DS4_METAL_HAS_TENSOR, a preprocessor macro of the Metal library source.
use strict;
use warnings;

my ($def_file, @sources) = @ARGV;
my (%def, %read);

open my $def, '<', $def_file or die "env-check: $def_file: $!\n";
while (<$def>) {
    $def{$1} = 1 if /^DS4_ENV\((DS4_[A-Z0-9_]+),/;
}

for my $file (@sources) {
    open my $fh, '<', $file or die "env-check: $file: $!\n";
    my $text = do { local $/; <$fh> };
    $text =~ s/glm_graph_env_(?:present|value)\(\s*"DS4_ROCM_\w+"//g;
    $read{$1} = 1 while $text =~ /"(DS4_[A-Z0-9_]+)"/g;
}
delete @read{qw(DS4_IMAGE_ DS4_METAL_HAS_TENSOR)};

my @new = grep { !$def{$_} } sort keys %read;
my @old = grep { !$read{$_} } sort keys %def;
print "env-check: read but not classified in $def_file: $_\n" for @new;
print "env-check: classified but no longer read, remove from $def_file: $_\n" for @old;
exit 1 if @new || @old;
printf "env-check: %d DS4_* variables classified\n", scalar keys %def;

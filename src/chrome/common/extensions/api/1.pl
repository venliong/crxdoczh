#!/usr/bin/perl

my $skip_next = 0;
my $line = 1;

while(<>) {
  if ($skip_next == 1) {
    $skip_next = 0;
    next;
  }

  if(s#^//@##) {
    $skip_next = 1;
  }

  print $_;
  ++$line;
}


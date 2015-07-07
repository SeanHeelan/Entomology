<?php
$doc1 = new DOMDocument('1.0', 'UTF-8');
$a = $doc1->createElement('el_a');
$a->appendChild($doc1);

// Increment the reference count on the xmlDoc to avoid triggering a
// double-free error check when $a is destroyed
$b = $doc1->createElement('el_b');

// ensure free(xmlNode->content) results in free(0)
$doc1->standalone = 0;
// Destroy a, and its child doc1
$a = 0;
?>

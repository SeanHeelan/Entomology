<?php
$dom = new DOMDocument('1.0', 'UTF-8');
$element = $dom->appendChild(new DOMElement('root'));
$comment = new DOMComment("Comment 0");
$comment = $element->appendChild($comment);

// refcount == 3
$comment->__construct("Comment 1");
// refcount == 2
$comment->__construct("Comment 2");
// refcount == 1
$comment->__construct("Comment 3"); 
// refcount == 0, object->document->ptr and object->document are freed
?>

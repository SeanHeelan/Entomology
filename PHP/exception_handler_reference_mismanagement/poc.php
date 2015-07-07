<?php

// Bug Details
// 0. At location A the error handler is triggered
// 1. At location B the error handler sets the current exception handler
// 	to a new instance of ExceptionHandler. This has the effect of 
//	creating a new zval (referring to the handler object) and storing 
//	a pointer to it in EG(user_exception_handler).
// 2. At location C an exception is thrown. Because an exception handler
//	has been registered it will be called. As part of this process 
//	the zval pointer is retrieved from EG(user_exception_handler) and
//	stored in EG(current_execute_data)->object.
// 2. At location D ZEND_FUNCTION(debug_backtrace) is invoked. This 
//	function creates a new array zval and then iterates over the 
//	backtrace of PHP functions, filling in the array with backtrace 
//	information as it goes. EG(current_execute_data) holds info on 
//	the currently executing function and is linked, recursively, to 
//	previous items via the prev_execute_data field. The first of these
//	previous items will refer to the zval pointer allocated in step 1
// 	via its object attribute (see step 2). Thus the zval pointer in 
//	EG(user_exception_handler) is added to the newly created array and
//	has its reference count incremented by 1. As the result of 
//	debug_backtrace is assigned to backtrace the array zval will be
//	added to the object store.
// 3. At location E another error is triggered, resulting in the error 
//	handler being called once again. On this occasion the call to 
//	set_exception_handler at location B will exhibit slightly 
//	different behaviour. Because there is already a user specified 
//	exception handler in EG(user_exception_handler) this will first of
//	all be pushed onto the EG(user_exception_handlers) stack before the 
//	new exception handler is installed. When this push takes place the
//	reference count of the zval in EG(user_exception_handler) is not
//	incremented.
// 4. The error generated at location E is not handled and the interpreter
//	will exit as a result. When this occurs zend_ptr_stack_clean is 
//	invoked and passed the EG(user_exception_handlers) stack. The only 
//	item on this stack will be the zval allocated in step 1 and later
//	added to the backtrace array in step 2.	It will be deallocated 
//	without any check taking place on its reference count. The outcome
//	of this is that the backtrace array now contains a reference to a 
//	freed variable. Later in the interpreter shutdown sequence a 
//	segmentation fault will occur when this reference is processed as
//	part of destructing the array.

class ExceptionHandler {
	public function __invoke (Exception $e)
	{
		// D
		$backtrace = debug_backtrace();
		// E
		$a['err_1'];
	}
}

set_error_handler(function()
{
	// B
	set_exception_handler(new ExceptionHandler());
	// C
	throw new Exception;
});

// A
$a['err_0'];
?>

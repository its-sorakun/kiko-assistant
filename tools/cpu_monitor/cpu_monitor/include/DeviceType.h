// Copyright (C) 2026 its-sorakun
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

//===----------------------------------------------------------------------===//
//====  Copyright (c) 2023 Advanced Micro Devices, Inc.  All rights reserved.
//
//               Developed by: Advanced Micro Devices, Inc.

/*!
* @file DeviceType.h
* @brief Device type header file
*/

#ifndef _DEVICE_TYPE_H_
#define _DEVICE_TYPE_H_

#ifdef DEVICE_EXPORTS
#define DEVICE_API __declspec(dllexport)
#else
#define DEVICE_API 
#endif

/*!
* @details
*	Each device type has a corresponding interface class.
*	When creating a new device type, make sure the type number is larger than the value of dtPluginDevice.
*/

enum AOD_DEVICE_TYPE
{
	dtInvalid = -1,
	/// ICPU
	dtCPU,
	/// IBIOS
	dtBIOS,	
};

#endif	//_DEVICE_TYPE_H_

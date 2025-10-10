/// GoMuseum 相机页面
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';
import 'package:gomuseum_app/ui/components/buttons/primary_button.dart';
import 'package:gomuseum_app/ui/components/buttons/icon_button_widget.dart';

class CameraPage extends StatelessWidget {
  const CameraPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // 相机预览区域 (占位)
          Center(
            child: Container(
              color: Colors.grey[900],
              child: const Center(
                child: Icon(
                  Icons.camera_alt,
                  size: 100,
                  color: Colors.white54,
                ),
              ),
            ),
          ),
          
          // 顶部工具栏
          SafeArea(
            child: Padding(
              padding: EdgeInsets.all(AppDimensions.spacing16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  AppIconButton(
                    icon: Icons.close,
                    onPressed: () => Navigator.pop(context),
                    color: Colors.white,
                  ),
                  AppIconButton(
                    icon: Icons.flash_auto,
                    onPressed: () {},
                    color: Colors.white,
                  ),
                ],
              ),
            ),
          ),
          
          // 底部控制栏
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              child: Padding(
                padding: EdgeInsets.all(AppDimensions.spacing24),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    AppIconButton(
                      icon: Icons.photo_library,
                      onPressed: () {},
                      color: Colors.white,
                      size: 32,
                    ),
                    // 拍照按钮
                    GestureDetector(
                      onTap: () {},
                      child: Container(
                        width: 80,
                        height: 80,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 4),
                        ),
                        child: Container(
                          margin: const EdgeInsets.all(4),
                          decoration: const BoxDecoration(
                            color: Colors.white,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ),
                    ),
                    AppIconButton(
                      icon: Icons.flip_camera_ios,
                      onPressed: () {},
                      color: Colors.white,
                      size: 32,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

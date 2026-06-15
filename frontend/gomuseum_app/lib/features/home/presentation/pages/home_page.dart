/// GoMuseum 主页
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';
import 'package:gomuseum_app/ui/layouts/app_scaffold.dart';
import 'package:gomuseum_app/ui/components/cards/museum_card.dart';
import 'package:gomuseum_app/ui/components/cards/artwork_card.dart';
import 'package:gomuseum_app/ui/components/buttons/primary_button.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'GoMuseum',
      showBackButton: false,
      showBottomNav: true,
      currentNavIndex: _currentIndex,
      onNavTap: (index) {
        setState(() {
          _currentIndex = index;
        });
      },
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Hero区域 - 扫描艺术品按钮
          _buildHeroSection(),

          SizedBox(height: AppDimensions.spacing24),

          // 附近博物馆
          _buildNearbyMuseums(),

          SizedBox(height: AppDimensions.spacing24),

          // 热门艺术品
          _buildPopularArtworks(),
        ],
      ),
    );
  }

  Widget _buildHeroSection() {
    return Container(
      height: MediaQuery.of(context).size.height * 0.4,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.primary,
            AppColors.primary.withValues(alpha: 0.8),
          ],
        ),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.camera_alt,
              size: 64,
              color: Colors.white,
            ),
            SizedBox(height: AppDimensions.spacing16),
            Text(
              '扫描艺术品',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
            ),
            SizedBox(height: AppDimensions.spacing8),
            Text(
              '用相机识别博物馆展品',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Colors.white.withValues(alpha: 0.9),
                  ),
            ),
            SizedBox(height: AppDimensions.spacing24),
            PrimaryButton(
              text: '开始识别',
              icon: Icons.camera,
              backgroundColor: AppColors.secondary,
              onPressed: () {
                // TODO: 导航到相机页面
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNearbyMuseums() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.symmetric(horizontal: AppDimensions.spacing16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '附近博物馆',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              TextButton(
                onPressed: () {},
                child: const Text('查看全部'),
              ),
            ],
          ),
        ),
        SizedBox(height: AppDimensions.spacing12),
        SizedBox(
          height: 220,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: EdgeInsets.symmetric(horizontal: AppDimensions.spacing16),
            itemCount: 5,
            separatorBuilder: (_, __) =>
                SizedBox(width: AppDimensions.spacing12),
            itemBuilder: (context, index) {
              return MuseumCard(
                imageUrl: 'https://picsum.photos/400/225?random=$index',
                name: '博物馆 ${index + 1}',
                address: '地址 ${index + 1}',
                openingHours: '09:00 - 18:00',
                distance: (index + 1) * 1.5,
                onTap: () {},
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildPopularArtworks() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.symmetric(horizontal: AppDimensions.spacing16),
          child: Text(
            '热门艺术品',
            style: Theme.of(context).textTheme.titleLarge,
          ),
        ),
        SizedBox(height: AppDimensions.spacing12),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: EdgeInsets.symmetric(horizontal: AppDimensions.spacing16),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: AppDimensions.spacing12,
            mainAxisSpacing: AppDimensions.spacing12,
            childAspectRatio: 0.75,
          ),
          itemCount: 6,
          itemBuilder: (context, index) {
            return ArtworkCard(
              imageUrl: 'https://picsum.photos/300/400?random=${index + 10}',
              title: '艺术品 ${index + 1}',
              artist: '艺术家 ${index + 1}',
              confidence: 0.85 + (index * 0.02),
              heroTag: 'artwork_$index',
              onTap: () {},
            );
          },
        ),
      ],
    );
  }
}

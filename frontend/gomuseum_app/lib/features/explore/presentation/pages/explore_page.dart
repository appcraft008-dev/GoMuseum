/// GoMuseum 探索页面
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/dimensions.dart';
import 'package:gomuseum_app/ui/components/cards/museum_card.dart';

class ExplorePage extends StatelessWidget {
  const ExplorePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('探索'),
      ),
      body: Column(
        children: [
          // 搜索栏
          Padding(
            padding: EdgeInsets.all(AppDimensions.spacing16),
            child: TextField(
              decoration: InputDecoration(
                hintText: '搜索博物馆或艺术品',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius:
                      BorderRadius.circular(AppDimensions.radiusMedium),
                ),
              ),
            ),
          ),

          // 筛选标签
          SizedBox(
            height: 50,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding:
                  EdgeInsets.symmetric(horizontal: AppDimensions.spacing16),
              children: [
                _buildFilterChip(context, '全部', true),
                _buildFilterChip(context, '博物馆', false),
                _buildFilterChip(context, '艺术品', false),
                _buildFilterChip(context, '附近', false),
              ],
            ),
          ),

          // 结果列表
          Expanded(
            child: ListView.builder(
              padding: EdgeInsets.all(AppDimensions.spacing16),
              itemCount: 5,
              itemBuilder: (context, index) {
                return Padding(
                  padding: EdgeInsets.only(bottom: AppDimensions.spacing16),
                  child: MuseumCard(
                    imageUrl:
                        'https://picsum.photos/400/225?random=${index + 20}',
                    name: '博物馆 ${index + 1}',
                    address: '地址 ${index + 1}',
                    openingHours: '09:00 - 18:00',
                    distance: (index + 1) * 2.0,
                    onTap: () {},
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(BuildContext context, String label, bool selected) {
    return Padding(
      padding: EdgeInsets.only(right: AppDimensions.spacing8),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        onSelected: (value) {},
      ),
    );
  }
}
